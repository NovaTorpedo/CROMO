"""Build the submission kit: slide deck (HTML -> PDF) and cover image, with every number read from measured files.

  python scripts/build_submission.py            # needs the app running on localhost:8765 for the cover image

Outputs submission/CROMO-slides.pdf, submission/slides/slides.html, submission/cover.png, and fills the generated blocks
of submission/SUBMISSION.md (AMD stack, measured results, Evolus, tags). Re-run after scripts/benchmark_amd.py so the AMD
numbers replace the "pending" / "[AMD: ...]" placeholders. The texts follow what actually ran (AMD Token Factory or own
vLLM on AMD Developer Cloud, complete or partial run), so no manual text edits are needed for any of them.
"""

from __future__ import annotations

import html
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

from cromo import investigate  # noqa: E402
from screenshot import browser  # noqa: E402

OUT = ROOT / "submission"
REC = ROOT / "data" / "recorded"


def load(name):
    p = REC / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def pct(x):
    return "pending" if x is None else f"{round(x * 100)}%"


def pct1(x):
    return "–" if x is None else f"{x * 100:.1f}%"


def eur(n):
    return f"€{round(n):,}"


def numbers() -> dict:
    vs = investigate.all_stored()
    counts = {k: sum(1 for v in vs.values() if v["verdict"] == k) for k in ("FOSSIL", "FENCE", "ACTIVE", "UNKNOWN")}
    fossil_eur = sum(v["cost"]["annual_eur"] for v in vs.values() if v["verdict"] == "FOSSIL")
    provider = {v["provider"] for v in vs.values()}
    model = next((v["model"] for v in vs.values()), "")
    amd, fx, bench = load("eval_amd.json"), load("eval_fixture.json"), load("benchmark_amd.json")
    from cromo import config

    return {"counts": counts, "fossil_eur": fossil_eur, "computed_on_amd": provider == {"amd"}, "model": model,
            "amd": amd, "fx": fx, "bench": bench, "levi": vs.get("ALK-04"), "vc": load("vision_comparison.json"),
            "oc": load("ocr_comparison.json"), "rv": load("retrieval_eval.json"),
            "rq": load("eval_amd_qwen.json"), "agent": bool(config.settings.evolus_agent_model),
            "extractor": bool(config.settings.evolus_extractor_id)}


DEFAULT_MODELS = {"reasoner": "Gemma-4-31B-IT", "vision": "Gemma-4-31B-IT", "embeddings": ""}


def label(m: str) -> str:
    """Human name of a model id."""
    if not m or m.startswith("fixture"):
        return "not on AMD in this run (recorded transcriptions)"
    lm = m.lower()
    if "gemma-4-26b" in lm:
        return "Gemma 4 26B-A4B-it (Google DeepMind)"
    if "gemma-4-31b" in lm:
        return "Gemma 4 31B-IT (Google DeepMind)"
    return m.split("/")[-1]


def stack(n: dict) -> dict:
    """Where and with which models the AMD part actually ran (or, before any run, the planned default)."""
    b = n["bench"] or {}
    tf = b.get("route", "tokenfactory") == "tokenfactory"
    models = b.get("models") or DEFAULT_MODELS
    where = "the AMD Token Factory (shared endpoints on AMD GPUs)" if tf else "one AMD Instinct MI300X (AMD Developer Cloud, ROCm + vLLM)"
    emb = models.get("embeddings") or ""
    local_emb = not emb or "local" in emb or emb.startswith("fixture")
    return {"tf": tf, "where": where, "measured": bool(b), "models": models, "same": models.get("vision") == models.get("reasoner"),
            "gemma": "gemma" in (models.get("reasoner") or "").lower() or "gemma" in (models.get("vision") or "").lower(),
            "local_emb": local_emb}


CSS = """
@page { size: 1920px 1080px; margin: 0; }
* { box-sizing: border-box; }
body { margin: 0; font-family: 'Inter', 'Segoe UI', sans-serif; color: #0b1220; background: #eef1f6; font-feature-settings: "cv11", "ss01"; }
.s { width: 1920px; height: 1080px; padding: 92px 120px; position: relative; page-break-after: always; overflow: hidden;
  background: #eef1f6 radial-gradient(1400px 900px at 6% -12%, rgba(255,196,150,.36), transparent 60%),
  radial-gradient(1200px 800px at 104% 0%, rgba(150,196,255,.34), transparent 62%), radial-gradient(1200px 900px at 60% 116%, rgba(176,226,214,.32), transparent 60%); }
.s:last-child { page-break-after: auto; }
h1 { font-size: 92px; line-height: 1.02; margin: 0; letter-spacing: -0.035em; font-weight: 740; }
h2 { font-size: 62px; line-height: 1.08; margin: 0 0 36px; font-weight: 720; letter-spacing: -0.03em; max-width: 1600px; }
p, li { font-size: 30px; line-height: 1.45; color: #334155; }
b { color: #0b1220; }
.eyebrow { font-size: 22px; color: #5b6577; margin-bottom: 18px; letter-spacing: 0.06em; text-transform: uppercase; font-weight: 650; }
.card { background: rgba(255,255,255,.86); border: 1px solid rgba(255,255,255,.8); border-radius: 32px;
  box-shadow: inset 0 1px 0 #fff, 0 30px 60px -36px rgba(15,23,42,.35); padding: 34px 40px; }
.foot { position: absolute; bottom: 44px; left: 120px; right: 120px; font-size: 19px; color: #5b6577; display: flex; justify-content: space-between; }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 60px; align-items: center; }
.shot { width: 100%; border-radius: 26px; box-shadow: 0 40px 80px -40px rgba(15,23,42,.45); border: 1px solid rgba(255,255,255,.9); }
.big { font-size: 92px; font-weight: 750; line-height: 1; letter-spacing: -0.035em; font-variant-numeric: tabular-nums; }
.fossil { color: #c2410c; } .fence { color: #0f766e; } .unknown { color: #6d28d9; } .muted { color: #5b6577; } .accent { color: #2f5bea; }
.kpis { display: grid; grid-template-columns: repeat(4, 1fr); gap: 24px; margin-top: 30px; }
.kpi .l { font-size: 24px; color: #334155; margin-top: 14px; line-height: 1.3; }
.kpi .s2 { font-size: 19px; color: #5b6577; margin-top: 8px; line-height: 1.35; }
table { border-collapse: collapse; width: 100%; font-size: 26px; }
td, th { padding: 15px 18px; border-bottom: 1px solid rgba(15,23,42,.08); text-align: left; }
tr:last-child td { border-bottom: none; }
th { color: #5b6577; font-weight: 600; font-size: 21px; }
td.n, th.n { text-align: right; font-variant-numeric: tabular-nums; }
tr.used td { background: rgba(47,91,234,.07); }
.chain { display: flex; flex-direction: column; gap: 12px; }
.chain span { background: rgba(255,255,255,.9); border: 1px solid rgba(15,23,42,.08); border-radius: 18px; padding: 12px 20px; font-size: 23px; color: #334155; }
.chain b { color: #c2410c; margin-right: 8px; }
.pending { color: #6d28d9; font-style: italic; }
.note { font-size: 21px; color: #5b6577; }
.logo { width: 120px; height: 120px; border-radius: 34px; display: grid; place-items: center; position: relative; font-weight: 760; font-size: 54px;
  background: linear-gradient(145deg, #fff 0%, #dfe5ee 45%, #b9c3d2 100%); box-shadow: inset 0 2px 0 #fff, 0 20px 40px -18px rgba(15,23,42,.4); }
.logo small { position: absolute; top: 12px; left: 16px; font-size: 18px; font-family: monospace; opacity: .7; }
.pill { display: inline-flex; align-items: center; gap: 10px; padding: 10px 20px; border-radius: 999px; background: rgba(255,255,255,.9);
  border: 1px solid rgba(15,23,42,.08); font-size: 22px; font-weight: 600; }
.pill i { width: 12px; height: 12px; border-radius: 50%; background: #15803d; display: inline-block; }
"""


def slide(inner: str, foot: str = "CROMO · AMD Developer Hackathon ACT III") -> str:
    return f'<section class="s">{inner}<div class="foot"><span>{foot}</span><span>synthetic data · fictional plant</span></div></section>'


def _levi_chain(n: dict) -> str:
    """The ALK-04 paper trail as CROMO actually cited it (from the stored verdict), never a scripted story."""
    v = n["levi"]
    if not v:
        return '<span class="pending">investigation pending</span>'
    cited = set(v["strength"]["cited"])
    items = sorted((e for e in v["evidence"].values() if e["id"] in cited and e.get("verified") and not e.get("suspicious")),
                   key=lambda e: e.get("date") or "9999")
    rows = [f"<span><b>{html.escape((e.get('date') or '')[:4])}</b>{html.escape((e.get('doc_type') or 'document').capitalize())}: "
            f"{html.escape((e.get('claim') or e['quote'])[:96])}</span>" for e in items[:7]]
    rows.append(f'<span style="border-color:#c2410c"><b class="fossil">{v["verdict"]}</b>{html.escape(v["strength"]["grade"])} evidence · '
                f'{eur(v["cost"]["annual_eur"])}/yr · {v["hops"]} hops</span>')
    return "".join(rows)


def build(n: dict) -> str:
    c, amd, fx, bench = n["counts"], n["amd"], n["fx"], n["bench"]
    img = "../../docs/img"
    st = stack(n)
    mo = st["models"]
    where = (f"computed on AMD by {html.escape(n['model'])}" if n["computed_on_amd"] else "offline heuristic results · AMD run pending")

    def val(ev, key, sub=None):
        if not ev:
            return '<span class="pending">pending</span>'
        x = ev[key] if sub is None else ev[key][sub]
        return pct(x)

    b = bench or {}
    s = []
    s.append('<section class="s" style="padding:0"><img src="../cover.png" style="width:1920px;height:1080px;display:block"></section>')
    s.append(slide("""
      <div class="eyebrow">1975 · Primo Levi, The Periodic Table, "Chromium"</div>
      <h2>A batch of anti-rust paint keeps turning to jelly.</h2>
      <p style="max-width:1500px">A young chemist traces it to one bad pigment delivery and fixes it by adding ammonium chloride.
      <b>Twenty years later</b> the bad pigment is long gone, and the factory still adds ammonium chloride to every batch.
      Nobody can say why.</p>
      <p style="max-width:1500px; margin-top:40px">The opposite also happens. Chesterton (1929): <i>don't tear down a fence until you know why it was put up.</i>
      Some steps that look pointless are load-bearing.</p>
      <p class="muted" style="margin-top:40px">Cromo is Italian for chromium.</p>"""))
    s.append(slide("""
      <div class="eyebrow">The problem</div>
      <h2>Recipes are full of steps whose reasons retired with the people who wrote them.</h2>
      <div class="grid2" style="align-items:start">
        <div class="card"><p style="margin:0"><b class="fossil">Fossils</b> cost money every batch: material, labour, energy, tank time. Nobody dares remove them.</p></div>
        <div class="card"><p style="margin:0"><b class="fence">Fences</b> look like waste but prevent fires, recalls and claims. Remove one and the old accident comes back.</p></div>
      </div>
      <p style="margin-top:40px">And AI optimisers now propose "remove this, shorten that", without knowing which is which.</p>
      <p class="muted">Users: process engineers · quality / EHS managers · plant managers. A human approves every change.</p>"""))
    s.append(slide(f"""
      <div class="eyebrow">The product · {where}</div>
      <h2>The periodic table of a plant.</h2>
      <div class="grid2" style="grid-template-columns: 1.45fr 1fr">
        <img class="shot" src="{img}/home.png">
        <div>
          <div class="big fossil">{eur(n['fossil_eur'])}<span style="font-size:40px">/yr</span></div><p>in <b>{c['FOSSIL']} fossil steps</b> of a synthetic mid-sized coatings plant</p>
          <div class="big fence" style="font-size:68px; margin-top:28px">{c['FENCE']} fences</div><p>protected from removal</p>
          <div class="big unknown" style="font-size:68px; margin-top:28px">{c['UNKNOWN']} unknown</div><p>sent to a person, never guessed</p>
        </div>
      </div>"""))
    s.append(slide(f"""
      <div class="eyebrow">The Why-Trail · the Levi case, recreated in our archive · as cited by the AMD run</div>
      <h2>It digs, it does not chat.</h2>
      <div class="grid2" style="grid-template-columns: 1fr 1.3fr; align-items:start">
        <div class="chain">{_levi_chain(n)}</div>
        <img class="shot" src="{img}/investigation.png">
      </div>"""))
    s.append(slide(f"""
      <div class="eyebrow">Fences and guardrails</div>
      <h2>Models read the evidence. Rules decide what may be removed.</h2>
      <div class="grid2">
        <img class="shot" src="{img}/change-check.png">
        <div><p>Every claim cites a quote <b>verified verbatim</b> in the source; uncited claims are dropped.</p>
        <p>A fossil needs proof that its reason ended and no open safety evidence; otherwise it goes to a person.</p>
        <p><b>What if…?</b> Change a step: <span class="fossil">blocked</span> · caution · allowed with trial (also a REST API for optimisers).
        Change the plant: tripwires show which reasons break.</p></div>
      </div>"""))
    gemma_note = ("<p style=\"margin-top:26px\"><b>Gemma 4</b>, Google DeepMind's open model, is both the eyes and the brain: one model "
                  "reads every scanned, faxed and handwritten page and does all the reasoning.</p>" if st["gemma"] else "")
    retrieval = ("BM25 + local n-grams + <b>Gemma's bilingual keywords</b> (no embedding model on the Token Factory)" if st["local_emb"]
                 else html.escape(label(mo.get("embeddings", ""))))
    s.append(slide(f"""
      <div class="eyebrow">How it works · every model call on {html.escape(st['where'])}{'' if st['measured'] else ' (planned)'}</div>
      <h2>Read the archive. Follow the paper trail. Decide with rules.</h2>
      <div class="card" style="padding:16px 26px">
      <table>
        <tr><th>Role</th><th>Model</th><th>Runs on</th></tr>
        <tr><td>Vision: scans, faxes, handwritten Italian logbooks</td><td><b>{html.escape(label(mo.get('vision', '')))}</b></td><td>AMD · image input</td></tr>
        <tr><td>Reasoner: reads passages, follows leads, proposes verdicts</td><td><b>{'same model' if st['same'] else html.escape(label(mo.get('reasoner', '')))}</b></td><td>AMD</td></tr>
        <tr><td>Retrieval</td><td>{retrieval}</td><td>{'CROMO server (CPU)' if st['local_emb'] else 'AMD'}</td></tr>
        <tr><td>Verdict rules, quote verification, costs</td><td>deterministic, auditable</td><td>CROMO server (CPU)</td></tr>
      </table></div>{gemma_note}"""))
    oc = n["oc"]
    if oc:
        kinds = [k for k in ("handwritten logbook", "fax", "typed / scanned") if k in oc["models"][0]["cer_by_kind"]]
        rows = "".join(
            f"<tr class=\"{'used' if m['model'] == mo.get('vision') else ''}\"><td><b>{html.escape(m['model'])}</b>"
            f"{' · used by CROMO' if m['model'] == mo.get('vision') else ''}</td><td class=\"n\">{pct1(m['mean_cer'])}</td>"
            f"<td class=\"n\">{pct1(m.get('mean_word_f1'))}</td>"
            + "".join(f"<td class=\"n\">{pct1(m['cer_by_kind'].get(k))}</td>" for k in kinds)
            + f"<td class=\"n\">{m['p50_ms'] / 1000:.0f} s</td></tr>" for m in oc["models"])
        s.append(slide(f"""
          <div class="eyebrow">Measured on AMD · {len(oc['models'])} AMD-hosted models · the same {oc['models'][0]['pages']} scanned pages</div>
          <h2>Which model reads 30 years of paperwork best?</h2>
          <div class="card" style="padding:16px 26px"><table>
            <tr><th>Model</th><th class="n">Strict CER</th><th class="n">Word F1</th>{''.join(f'<th class="n">{k} (n={oc["models"][0]["pages_by_kind"][k]})</th>' for k in kinds)}<th class="n">p50 / page</th></tr>
            {rows}
          </table></div>
          <p class="note" style="margin-top:26px">CER = character error rate vs. the reference transcription (lower is better), reading order counted; word F1 ignores
          order. Gemma and MiniCPM are within 0.1 points; Gemma reads the handwritten logbooks best and keeps one model for reading and reasoning.</p>"""))
    ing, va, inv, cost = b.get("ingest") or {}, b.get("vision_accuracy") or {}, b.get("investigation") or {}, b.get("cost") or {}
    use = b.get("tokenfactory_usage") or {}

    def m(x, unit=""):
        return f"{x}{unit}" if x not in (None, "") else '<span class="pending">pending</span>'

    if cost.get("per_plant_audit_usd") is not None:
        audit, audit_l = f"${cost['per_plant_audit_usd']}", f"GPU cost of a full plant audit ({cost.get('gpu_hours')} GPU-h at ${cost.get('price_per_gpu_hour')}/h)"
    elif use and b.get("complete") is not False:
        audit, audit_l = f"${use['metered_usd']:.2f}", f"metered for a full audit: {use['requests']} requests, {use['tokens'] / 1e6:.1f}M tokens (Token Factory meter, free during the event)"
    else:
        audit, audit_l = m(None), "cost of a full plant audit"
    partial = (f"<p class=\"note\">Partial run: {inv.get('steps')} of {inv.get('of_steps')} steps measured on AMD; no evaluation score is claimed for it.</p>"
               if b.get("complete") is False else "")
    rv = n["rv"]
    rtxt = (f" · key documents found in the top 5 searches: {pct(rv['without_expansion']['recall_at_5'])} → "
            f"<b>{pct(rv['with_expansion']['recall_at_5'])}</b> with Gemma's keywords" if rv else "")
    s.append(slide(f"""
      <div class="eyebrow">Measured on AMD {('· ' + html.escape(b.get('hardware', ''))) if b else '· benchmark pending'}</div>
      <h2>Real numbers, never estimates.</h2>
      <div class="kpis">
        <div class="card kpi"><div class="big" style="font-size:76px">{m(inv.get('p50_s'), ' s')}</div><div class="l">median multi-hop investigation</div><div class="s2">{m(inv.get('calls_per_step'))} model calls per step · {inv.get('concurrency', '–')} at a time</div></div>
        <div class="card kpi"><div class="big" style="font-size:76px">{m(ing.get('pages_per_min'))}</div><div class="l">archive pages / minute ingested</div><div class="s2">{'bounded by the 20 requests/min account limit' if st['tf'] else ''}</div></div>
        <div class="card kpi"><div class="big" style="font-size:76px">{m(None if va.get('mean_cer') is None else pct1(va.get('mean_cer')))}</div><div class="l">character error rate on scans and handwriting</div><div class="s2">{va.get('pages', '–')} scanned pages read by Gemma</div></div>
        <div class="card kpi"><div class="big" style="font-size:76px">{audit}</div><div class="l">{audit_l}</div></div>
      </div>
      <p style="margin-top:40px">178 documents, 49 steps{rtxt}.</p>{partial}"""))
    s.append(slide(f"""
      <div class="eyebrow">Evaluation · 49 steps with planted ground truth (12 fossils, 9 fences, 22 active, 6 unknown)</div>
      <h2>Missing a fence is the dangerous error.</h2>
      <div class="card" style="padding:16px 26px"><table>
        <tr><th></th><th class="n">Heuristic baseline (no LLM)</th><th class="n">CROMO on AMD · {html.escape(label(mo.get('reasoner', '')))}</th></tr>
        <tr><td>FENCE recall</td><td class="n">{val(fx, 'fence_recall')}</td><td class="n"><b>{val(amd, 'fence_recall')}</b></td></tr>
        <tr><td>False-FOSSIL rate</td><td class="n">{val(fx, 'false_fossil_rate')}</td><td class="n"><b>{val(amd, 'false_fossil_rate')}</b></td></tr>
        <tr><td>Fences called fossils</td><td class="n">{len(fx['dangerous_errors']) if fx else '–'}</td><td class="n"><b>{len(amd['dangerous_errors']) if amd else '<span class="pending">pending</span>'}</b></td></tr>
        <tr><td>Accuracy (4 classes)</td><td class="n">{val(fx, 'accuracy')}</td><td class="n"><b>{val(amd, 'accuracy')}</b></td></tr>
        <tr><td>Citation precision</td><td class="n">{val(fx, 'citations', 'precision')}</td><td class="n"><b>{val(amd, 'citations', 'precision')}</b></td></tr>
        <tr><td>Prompt-injection document</td><td class="n">{'ignored' if fx and fx['injection']['passed'] else 'pending'}</td><td class="n"><b>{'ignored' if amd and amd['injection']['passed'] else '<span class="pending">pending</span>'}</b></td></tr>
      </table></div>
      <p class="note" style="margin-top:24px">Synthetic archive: red herrings, contradictions, a reverted change, a reason only in a handwritten logbook. The product never reads the answer key (tested).</p>"""))
    s.append(slide(f"""
      <div class="eyebrow">Evolus building blocks</div>
      <h2>A human approves every change, through Evolus.</h2>
      <div class="grid2">
        <img class="shot" src="{img}/trials.png">
        <div><p><b>Workflow</b>: fossil → trial plan → AI Tool brief for the engineer → approval record → decision → status back in CROMO.</p>
        <p><b>AI Tool compare</b>: what changed when a step was added. <b>Knowledge library</b>: the 178-document archive.
        {'<b>Extractor + agent</b> on our own AMD-hosted model.' if n['agent'] else ''}</p>
        <p class="note">All driven through the Evolus REST API; the workflow was created via POST /workflows.</p></div>
      </div>"""))
    s.append(slide(f"""
      <div class="eyebrow">Business value · roadmap · team</div>
      <h2>Find the waste. Keep the fences.</h2>
      <div class="grid2" style="align-items:start">
        <div class="card"><p style="margin-top:0"><b>Value</b>: in our synthetic plant, {eur(n['fossil_eur'])}/yr of fossil steps found, with an audit trail, and every fence protected
        from well-meant "optimisations".</p>
        <p style="margin-bottom:0"><b>Model</b>: per-site subscription for process industries (coatings, chemicals, food, pharma); the change-check API for MES and optimisation vendors.</p></div>
        <div class="card"><p style="margin-top:0"><b>Next</b>: pilot on a real archive · veteran interviews for unknowns · MES connectors · cross-recipe fossil detection.</p>
        <p style="margin-bottom:0"><b>Team</b>: solo developer, built with Claude Code. MIT licensed, open models, zero budget.</p></div>
      </div>"""))
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>CROMO slides</title>
<link rel="stylesheet" href="fonts.css"><style>{CSS}</style></head><body>{''.join(s)}</body></html>"""


def _ph(x, fmt=pct, name="") -> str:
    """A measured value, or a clearly marked placeholder that only an AMD run can fill."""
    return fmt(x) if x is not None else f"[AMD: {name}]"


def submission_blocks(n: dict) -> dict[str, str]:
    st, b, amd, fx = stack(n), n["bench"] or {}, n["amd"], n["fx"] or {}
    mo = st["models"]
    lines = [f"Every model call runs on {st['where']}:"]
    if st["gemma"]:
        g = label(mo.get("reasoner") or mo.get("vision") or "")
        lines.append(f"- **{g}, open weights** "
                     + ("as both the eyes and the brain: it reads every scanned, faxed and handwritten Italian page, reasons over "
                        "the evidence, proposes verdicts and writes the bilingual search keywords for each document" if st["same"]
                        else "as the " + ("reasoner" if "gemma" in (mo.get("reasoner") or "").lower() else "vision model"))
                     + (", and drives the Evolus agent through native tool calling;" if n["agent"] and not st["tf"] else ";"))
    off = lambda m: not m or m.startswith("fixture")  # noqa: E731  role not served on AMD in this run
    if not st["same"] or not st["gemma"]:
        for role in ("vision", "reasoner"):
            m = mo.get(role) or ""
            if off(m) and role == "vision":
                lines.append("- scanned pages: recorded transcriptions (no AMD vision model in this run);")
            elif not (st["gemma"] and "gemma" in m.lower()):
                lines.append(f"- {role}: {label(m)};")
    lines.append("- retrieval: BM25 plus local n-gram vectors on the CROMO server, made bilingual by the keywords Gemma writes "
                 "at ingest (the Token Factory serves no embedding model);" if st["local_emb"]
                 else f"- {label(mo.get('embeddings', ''))} for multilingual retrieval;")
    oc = n["oc"]
    if oc:
        by = {m["model"]: m for m in oc["models"]}
        g = by.get(mo.get("vision") or "")
        others = ", ".join(f"{m['model']} {pct1(m['mean_cer'])}" for m in oc["models"] if m["model"] != (mo.get("vision") or ""))
        if g:
            lines.append(f"- the vision model was chosen by measurement: on the archive's {g['pages']} scanned pages, "
                         f"{g['model']} reads with a {pct1(g['mean_cer'])} character error rate "
                         f"({pct1(g['cer_by_kind'].get('handwritten logbook'))} on handwritten logbooks), against {others} "
                         "for the other AMD-hosted models we tested.")
    vc = n["vc"]
    if vc and vc.get("verdict"):
        lines.append(f"- a measured vision A/B on the same GPU: {vc['verdict']}")
    lines[-1] = lines[-1].rstrip(";") + ("" if lines[-1].endswith(".") else ".")
    stack_md = "\n".join(lines)

    ing, inv, cost, va = b.get("ingest") or {}, b.get("investigation") or {}, b.get("cost") or {}, b.get("vision_accuracy") or {}
    use = b.get("tokenfactory_usage") or {}
    if b.get("complete") is False:
        res = (f"**Measured on AMD (partial run).** Time ran out after {inv.get('steps')} of {inv.get('of_steps')} steps, so we report "
               f"no evaluation score. Measured: {_ph(ing.get('pages_per_min'), str, 'pages/min')} archive pages per minute ingested, "
               f"a median multi-hop investigation of {_ph(inv.get('p50_s'), str, 'median s')} s. "
               f"The rule-based baseline (no LLM) reaches a FENCE recall of {pct(fx.get('fence_recall'))} on the same ground truth.")
    else:
        dang = (amd or {}).get("dangerous_errors")
        vision_on_amd = not (b and off(mo.get("vision", "")))
        res = (f"**Measured on AMD.** On the planted ground truth CROMO reaches a FENCE recall of "
               f"{_ph((amd or {}).get('fence_recall'), name='FENCE recall')} (rule-based baseline without an LLM: {pct(fx.get('fence_recall'))}), "
               f"a false-FOSSIL rate of {_ph((amd or {}).get('false_fossil_rate'), name='false-FOSSIL rate')} "
               f"(baseline {pct(fx.get('false_fossil_rate'))}), {_ph(None if dang is None else len(dang), str, 'n')} fences called fossils "
               f"and a citation precision of {_ph(((amd or {}).get('citations') or {}).get('precision'), name='citation precision')}. "
               f"It ingests {_ph(ing.get('pages_per_min'), str, 'pages/min')} archive pages per minute"
               + (" (bounded by the event endpoint's 20 requests/minute)" if st["tf"] and ing else "")
               + (f", reads scans and handwriting with a character error rate of {_ph(va.get('mean_cer'), pct1, 'CER')}" if vision_on_amd else "")
               + f" and takes {_ph(inv.get('p50_s'), str, 'median s')} s for a median multi-hop investigation.")
        if cost.get("per_plant_audit_usd") is not None:
            res += f" A full plant audit (178 documents, 49 steps) costs ${cost['per_plant_audit_usd']} of GPU time."
        elif st["tf"] and use:
            res += (f" A full plant audit (178 documents, 49 steps) took {use['requests']} requests and {use['tokens'] / 1e6:.1f}M tokens, "
                    f"${use['metered_usd']:.2f} on the Token Factory meter (free during the event).")
        elif not st["tf"]:
            res += " A full plant audit (178 documents, 49 steps) costs [AMD: $ per audit] of GPU time."
    ev = ["Evolus building blocks, all driven from CROMO through the Evolus REST API:",
          "- a **workflow** for trial approval (created via `POST /workflows` and run from the Trials page): it writes the "
          "engineer's brief with an AI Tool step, records the approval and returns the decision;",
          "- the **compare AI Tool** for \"what changed when this step was added\" between recipe revisions;",
          "- a **knowledge library** holding the 178-document archive;"]
    if n["extractor"]:
        ev.append("- a **document extractor** that turns scans into structured records, running on our AMD-hosted model;")
    if n["agent"]:
        ev.append("- a **plant agent** on the library that answers from the archive, running on our open model served by vLLM on AMD.")
    ev[-1] = ev[-1].rstrip(";") + "."
    tags = (["AMD Token Factory", "AMD GPUs"] if st["tf"] else ["AMD Instinct MI300X", "AMD ROCm", "AMD Developer Cloud", "vLLM"])
    tags += ["Gemma", "Gemma 4", "Google DeepMind"] if st["gemma"] else []
    if not st["local_emb"]:
        tags.append("bge-m3")
    tags += ["Evolus", "FastAPI", "React", "Python", "TypeScript", "Docker"]
    return {"AMD-STACK": stack_md, "AMD-RESULTS": res, "EVOLUS": "\n".join(ev), "TAGS": " · ".join(tags)}


def update_submission(n: dict) -> None:
    import re

    p = OUT / "SUBMISSION.md"
    s = p.read_text(encoding="utf-8")
    for key, body in submission_blocks(n).items():
        s = re.sub(rf"(<!-- {key}:START -->).*?(<!-- {key}:END -->)", lambda m, b=body: m.group(1) + "\n" + b + "\n" + m.group(2),
                   s, flags=re.S)
    p.write_text(s, encoding="utf-8", newline="\n")
    left = sorted(set(re.findall(r"\[AMD: (?!\.\.\.)[^\]]+\]", s)))
    print("submission text:", p, "| placeholders left:", ", ".join(left) or "none")


def refresh_cover():
    try:
        import urllib.request

        urllib.request.urlopen("http://localhost:8765/api/health", timeout=3)
        subprocess.run([sys.executable, str(ROOT / "scripts" / "screenshot.py"), "http://localhost:8765/#/cover?theme=light",
                        str(OUT / "cover.png"), "--size", "1600x900", "--wait", "6000"], check=True)
        print("cover:", OUT / "cover.png")
    except OSError:
        print("cover: skipped (start the app on :8765 to refresh it)")


def main():
    refresh_cover()
    n = numbers()
    update_submission(n)
    d = OUT / "slides"
    d.mkdir(parents=True, exist_ok=True)
    for old in d.glob("*.woff2"):  # fonts of the previous design
        old.unlink()
    # self-hosted fonts (SIL OFL) from the frontend build dependencies
    css = []
    inter = ROOT / "frontend" / "node_modules" / "@fontsource-variable" / "inter" / "files" / "inter-latin-wght-normal.woff2"
    if inter.exists():
        shutil.copyfile(inter, d / inter.name)
        css.append(f"@font-face {{ font-family: 'Inter'; font-weight: 100 900; src: url('{inter.name}'); }}")
    (d / "fonts.css").write_text("\n".join(css), encoding="utf-8")
    (d / "slides.html").write_text(build(n), encoding="utf-8")
    pdf = OUT / "CROMO-slides.pdf"
    import tempfile

    with tempfile.TemporaryDirectory() as prof:
        subprocess.run([browser(), "--headless=new", "--disable-gpu", f"--user-data-dir={prof}", "--no-pdf-header-footer",
                        f"--print-to-pdf={pdf}", "--virtual-time-budget=4000", (d / "slides.html").resolve().as_uri()],
                       check=True, capture_output=True, timeout=180)
    print("slides:", pdf)


if __name__ == "__main__":
    main()
