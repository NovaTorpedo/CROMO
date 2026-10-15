"""Text utilities: normalisation, tokens, sentences, quote verification, injection heuristics."""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

STOP = set("""
a an the and or of to in on at for from by with without as is are was were be been being it its this that these those
into over under after before during per not no nor than then so such can may must shall should will would could
all any each every other our we you they he she his her their them there here which who whom whose what when where
why how also only up down out about above below between both more most less very via vs etc i e g eg ie
il lo la i gli le un una uno di da del della dei delle con su per tra fra che non come ma ed e o se nel nella
alla al allo agli sono è era sempre poi d ora ogni tutto tutti
step steps batch add added adding use used using before after min h kg l
""".split())

DOC_REF = re.compile(r"\b(?:DR|IR|NM|CR|SQ|LT|EQ|CM|QN|CL|WI|PM|RN|MM|AUD)-\d{4}-\d{2,3}\b")
STEP_ID = re.compile(r"\b(?:ALK|EPX|SOL|TNK|QC)-\d{2}\b", re.I)
WORD = re.compile(r"[A-Za-zÀ-ÿ0-9][A-Za-zÀ-ÿ0-9\-\.]*[A-Za-zÀ-ÿ0-9]|[A-Za-zÀ-ÿ0-9]")


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("’", "'").replace("“", '"').replace("”", '"').replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", s).strip()


def fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", norm(s).lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def stem(t: str) -> str:
    """Very light English stemmer (retaining->retain, samples->sample, added->add)."""
    if len(t) > 5 and t.endswith("ing"):
        return t[:-3]
    if len(t) > 4 and t.endswith("ed") and not t.endswith("eed"):
        return t[:-2]
    if len(t) > 3 and t.endswith("s") and not t.endswith(("ss", "us", "is")):
        return t[:-1]
    return t


def tokens(s: str, *, keep_stop: bool = False) -> list[str]:
    out = []
    for m in WORD.finditer(fold(s)):
        t = m.group(0).strip(".-")
        if not t:
            continue
        if not keep_stop and (t in STOP or len(t) < 2):
            continue
        out.append(stem(t) if t.isalpha() else t)
    return out


def sentences(s: str) -> list[str]:
    s = norm(s)
    parts = re.split(r"(?<=[.!?;])\s+(?=[A-Z0-9\"'(>])", s)
    return [p.strip() for p in parts if len(p.strip()) > 3]


def quote_in(quote: str, text: str, threshold: float = 0.88) -> bool:
    """True when `quote` appears (exactly or near-exactly) in `text`."""
    qn, tn = fold(quote), fold(text)
    if not qn or len(qn) < 8:
        return False
    if qn in tn:
        return True
    # sliding fuzzy match over windows of similar length (tolerates OCR noise)
    n = len(qn)
    best = 0.0
    step = max(1, n // 6)
    for i in range(0, max(1, len(tn) - n + 1), step):
        r = SequenceMatcher(None, qn, tn[i:i + n + 10], autojunk=False).ratio()
        best = max(best, r)
        if best >= threshold:
            return True
    return False


def best_sentence(text: str, terms: list[str]) -> str:
    sents = sentences(text) or [norm(text)]
    tset = set(terms)

    def score(s):
        toks = tokens(s)
        return sum(1 for t in toks if t in tset) + 0.01 * min(len(toks), 30)

    return max(sents, key=score)


INJECTION_PATTERNS = [
    re.compile(p, re.I) for p in [
        r"ignore (all |your )?(previous|prior|above) instructions",
        r"note (for|to) (ai|llm|language model)s?",
        r"you are (now )?(an?|the) (ai|assistant|system)",
        r"system prompt",
        r"classify (it|this|all|every)[^.]{0,40} as (fossil|fence|active|unknown)",
        r"disregard (the|all|any) (rules|instructions)",
    ]
]


def injection_suspect(text: str) -> bool:
    return any(p.search(text) for p in INJECTION_PATTERNS)


def overlap(a: list[str], b: list[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / min(len(sa), len(sb))
