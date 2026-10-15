"""Build the submission kit: slide deck (HTML -> PDF) and cover image, with every number read from measured files.

  python scripts/build_submission.py            # needs the app running on localhost:8765 for the cover image

Outputs submission/CROMO-slides.pdf, submission/slides/slides.html, submission/cover.png, and fills the generated blocks
of submission/SUBMISSION.md (AMD stack + measured results). Re-run after scripts/benchmark_amd.py so the AMD numbers
replace the "pending" / "[AMD: ...]" placeholders. The stack text follows what actually ran (Developer Cloud or Token
Factory, complete or partial run), so no manual text edits are needed for any of them.
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
            "rq": load("eval_amd_qwen.json"), "agent": bool(config.settings.evolus_agent_model),
            "extractor": bool(config.settings.evolus_extractor_id)}


DEFAULT_MODELS = {"reasoner": "google/gemma-4-26B-A4B-it", "vision": "google/gemma-4-26B-A4B-it", "embeddings": "BAAI/bge-m3"}


def stack(n: dict) -> dict:
    """Where and with which models the AMD part actually ran (or, before any run, the planned default)."""
    b = n["bench"] or {}
    tf = b.get("route") == "tokenfactory"
    models = b.get("models") or DEFAULT_MODELS
    where = "AMD Token Factory" if tf else "one AMD Instinct MI300X (AMD Developer Cloud, ROCm + vLLM)"

    def label(m: str) -> str:
        if not m or m.startswith("fixture"):
            return "not on AMD in this run (recorded transcriptions)"
        return "Gemma 4 26B-A4B-it (Google DeepMind)" if "gemma-4-26b" in m.lower() else m.split("/")[-1]

    return {"tf": tf, "where": where, "measured": bool(b), "models": models, "label": label,
            "same": models.get("vision") == models.get("reasoner"), "gemma": "gemma" in (models.get("reasoner") or "").lower()
            or "gemma" in (models.get("vision") or "").lower()}


CSS = """
@page { size: 1920px 1080px; margin: 0; }
* { box-sizing: border-box; }
body { margin: 0; font-family: 'IBM Plex Sans', 'Segoe UI', sans-serif; color: #1c1c1f; background: #f5f2eb; }
.s { width: 1920px; height: 1080px; padding: 96px 120px; position: relative; page-break-after: always; overflow: hidden; background: #f5f2eb; }
.s:last-child { page-break-after: auto; }
h1 { font-family: 'Fraunces', Georgia, serif; font-size: 84px; line-height: 1.05; margin: 0; letter-spacing: -1px; font-weight: 600; }
h2 { font-family: 'Fraunces', Georgia, serif; font-size: 64px; line-height: 1.1; margin: 0 0 36px; font-weight: 600; letter-spacing: -0.5px; }
p, li { font-size: 32px; line-height: 1.45; color: #3c3c42; }
.eyebrow { font-size: 24px; color: #86827a; margin-bottom: 18px; letter-spacing: 0.5px; }
.logo { display: inline-flex; align-items: center; gap: 22px; }
.tile { width: 110px; height: 110px; border-radius: 16px; background: #f2c230; display: grid; place-items: center; font-family: Georgia, serif; font-weight: 700; font-size: 54px; position: relative; color: #1f1903; }
.tile small { position: absolute; top: 8px; left: 11px; font-size: 18px; font-family: monospace; }
.word { font-family: Georgia, serif; font-size: 72px; letter-spacing: 10px; font-weight: 600; }
.foot { position: absolute; bottom: 48px; left: 120px; right: 120px; font-size: 20px; color: #86827a; display: flex; justify-content: space-between; }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 64px; align-items: center; }
.shot { width: 100%; border-radius: 14px; box-shadow: 0 24px 60px -24px rgba(40,30,10,.35); border: 1px solid #e6e0d4; }
.big { font-family: 'Fraunces', Georgia, serif; font-size: 96px; font-weight: 600; line-height: 1; }
.fossil { color: #cf6a0c; } .fence { color: #0d8a79; } .unknown { color: #7451c3; } .muted { color: #86827a; }
.kpis { display: grid; grid-template-columns: repeat(3, 1fr); gap: 48px; margin-top: 40px; }
.kpi { border-left: 6px solid #1c1c1f; padding-left: 24px; }
.kpi .l { font-size: 26px; color: #4a4a50; margin-top: 12px; }
table { border-collapse: collapse; width: 100%; font-size: 28px; }
td, th { padding: 16px 20px; border-bottom: 1px solid #e6e0d4; text-align: left; }
th { color: #86827a; font-weight: 500; font-size: 24px; }
.chain { display: flex; flex-wrap: wrap; gap: 14px; align-items: center; font-size: 26px; }
.chain span { background: #fff; border: 1px solid #e6e0d4; border-radius: 999px; padding: 10px 20px; }
.chain b { color: #c99a10; }
.pending { color: #b08ee6; font-style: italic; }
.note { font-size: 22px; color: #86827a; }
"""


def slide(inner: str, foot: str = "CROMO · AMD Developer Hackathon ACT III") -> str:
    return f'<section class="s">{inner}<div class="foot"><span>{foot}</span><span>synthetic data · fictional plant</span></div></section>'


def build(n: dict) -> str:
    c, amd, fx, bench = n["counts"], n["amd"], n["fx"], n["bench"]
    img = "../../docs/img"
    where = (f"computed on AMD by {html.escape(n['model'])}" if n["computed_on_amd"]
             else "offline heuristic results - AMD run pending")

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
      <b>Twenty years later</b> the bad pigment is long gone - and the factory still adds ammonium chloride to every batch.
      Nobody can say why.</p>
      <p style="max-width:1500px; margin-top:40px">The opposite also happens. Chesterton (1929): <i>don't tear down a fence until you know why it was put up.</i>
      Some steps that look pointless are load-bearing.</p>
      <p class="muted" style="margin-top:40px">Cromo is Italian for chromium.</p>"""))
    s.append(slide("""
      <div class="eyebrow">The problem</div>
      <h2>Recipes are full of steps whose reasons retired with the people who wrote them.</h2>
      <div class="grid2" style="align-items:start">
        <div><p><b class="fossil">Fossils</b> cost money every batch: material, labour, energy, tank time. Nobody dares remove them.</p></div>
        <div><p><b class="fence">Fences</b> look like waste but prevent fires, recalls and claims. Remove one and the old accident comes back.</p></div>
      </div>
      <p style="margin-top:30px">And AI optimisers now propose "remove this, shorten that" - without knowing which is which.</p>
      <p class="muted">Users: process engineers · quality / EHS managers · plant managers. A human approves every change.</p>"""))
    s.append(slide(f"""
      <div class="eyebrow">The product · {where}</div>
      <h2>The periodic table of a plant.</h2>
      <div class="grid2" style="grid-template-columns: 1.35fr 1fr">
        <img class="shot" src="{img}/home.png">
        <div>
          <div class="big fossil">{eur(n['fossil_eur'])}<span style="font-size:44px">/yr</span></div><p>in <b>{c['FOSSIL']} fossil steps</b> of a synthetic mid-sized coatings plant</p>
          <div class="big fence" style="font-size:72px; margin-top:30px">{c['FENCE']} fences</div><p>protected from removal</p>
          <div class="big unknown" style="font-size:72px; margin-top:30px">{c['UNKNOWN']} unknown</div><p>sent to a person - never guessed</p>
        </div>
      </div>"""))
    s.append(slide(f"""
      <div class="eyebrow">Live investigation · the Levi case, recreated in our archive</div>
      <h2>It digs, it does not chat.</h2>
      <div class="grid2" style="grid-template-columns: 1fr 1.25fr; align-items:start">
        <div class="chain" style="flex-direction:column; align-items:flex-start">
          <span><b>Recipe</b> step first appears 1996</span><span><b>1995</b> deviation: enamel turns to gel</span>
          <span><b>1995</b> lab test: pigment lot too alkaline</span><span><b>1995</b> change request: add NH4Cl "temporarily"</span>
          <span><b>1996</b> supplier fax: process fixed</span><span><b>2006</b> memo: chromate pigment phased out</span>
          <span><b>2007</b> new neutral pigment qualified</span><span><b>2020</b> lab: NH4Cl has no effect</span>
          <span style="border-color:#cf6a0c"><b class="fossil">FOSSIL</b> · strong evidence · {eur((n['levi'] or {}).get('cost', {}).get('annual_eur', 0))}/yr</span>
        </div>
        <img class="shot" src="{img}/investigation.png">
      </div>"""))
    s.append(slide(f"""
      <div class="eyebrow">Fences and guardrails</div>
      <h2>Models read the evidence. Rules decide what may be removed.</h2>
      <div class="grid2">
        <img class="shot" src="{img}/change-check.png">
        <div><p>Every claim cites a quote <b>verified verbatim</b> in the source; uncited claims are dropped.</p>
        <p>A fossil needs proof that its reason ended and no open safety evidence - otherwise it goes to a person.</p>
        <p><b>Before you change</b> - also a REST API for optimisers: <span class="fossil">blocked</span> · caution · allowed with trial.</p></div>
      </div>"""))
    s.append(slide(f"""
      <div class="eyebrow">Tripwires · forward-looking</div>
      <h2>When the plant changes, which reasons break?</h2>
      <div class="grid2">
        <div><p>Each recovered reason records its dependencies: suppliers, materials, equipment, regulations.</p>
        <p>Switch to a cheaper, crystallising epoxy resin and CROMO warns: the "useless" hot-box step is <b class="fossil">needed again</b>.</p>
        <p>Replace a solvent, and the fences that guarded against it may become fossils - re-investigate, trial, approve.</p></div>
        <img class="shot" src="{img}/tripwires.png">
      </div>"""))
    st = stack(n)
    mo = st["models"]
    serving = "AMD Token Factory" if st["tf"] else "vLLM · ROCm"
    gemma_note = ("<p style=\"margin-top:28px\"><b>Gemma 4</b>, Google DeepMind's open model, is both the eyes and the brain: one model "
                  "reads every scanned, faxed and handwritten page and does all the reasoning, with native image input and tool calling.</p>"
                  if st["gemma"] else "")
    s.append(slide(f"""
      <div class="eyebrow">How it works · the whole pipeline on {html.escape(st['where'])}{'' if st['measured'] else ' (planned)'}</div>
      <h2>Read the archive. Follow the paper trail. Decide with rules.</h2>
      <table>
        <tr><th>Role</th><th>Open model</th><th>On AMD</th></tr>
        <tr><td>Vision: scans, faxes, handwritten Italian logbooks</td><td>{html.escape(st['label'](mo.get('vision', '')))}</td><td>{serving} · image input</td></tr>
        <tr><td>Reasoner: reads passages, follows leads, proposes verdicts</td><td>{'same model' if st['same'] else html.escape(st['label'](mo.get('reasoner', '')))}</td><td>{serving} · tool calling</td></tr>
        <tr><td>Embeddings: multilingual retrieval</td><td>{html.escape(st['label'](mo.get('embeddings', '')))}</td><td>{serving}</td></tr>
      </table>{gemma_note}
      <p style="margin-top:28px">Ingestion → hybrid index → multi-hop investigation (9 hops max, streamed) → verified citations → evidence-strength rules → tripwires, change-check, trials.</p>"""))
    ing, va, inv, cost = b.get("ingest") or {}, b.get("vision_accuracy") or {}, b.get("investigation") or {}, b.get("cost") or {}

    def m(x, unit=""):
        return f"{x}{unit}" if x not in (None, "") else '<span class="pending">pending</span>'

    if cost.get("per_plant_audit_usd") is not None:
        audit = f"${cost['per_plant_audit_usd']}"
        price = f" · price ${cost.get('price_per_gpu_hour')}/GPU-h (AMD Developer Cloud list price)"
    elif b:
        audit, price = "n/a", ""
    else:
        audit, price = m(None), ""
    audit_note = ("" if not b or cost.get("per_plant_audit_usd") is not None else
                  " (partial run)" if b.get("complete") is False else " (Token Factory: no per-GPU billing)")
    vc = n["vc"]
    ab = ""
    if vc and vc.get("A", {}).get("mean_cer") is not None and vc.get("B", {}).get("mean_cer") is not None:
        ab = (f"<p>Vision A/B on the same scans: {html.escape(st['label'](vc['A']['model']))} CER <b>{pct(vc['A']['mean_cer'])}</b> vs "
              f"{html.escape(st['label'](vc['B']['model']))} CER <b>{pct(vc['B']['mean_cer'])}</b>.</p>")
    partial = (f"<p class=\"note\">Partial run: {inv.get('steps')} of {inv.get('of_steps')} steps measured on AMD before time ran out; "
               "no evaluation score is claimed for it.</p>" if b.get("complete") is False else "")
    s.append(slide(f"""
      <div class="eyebrow">Measured on AMD {('· ' + html.escape(b.get('hardware', ''))) if b else '· benchmark pending'}</div>
      <h2>Real numbers, never estimates.</h2>
      <div class="kpis">
        <div class="kpi"><div class="big" style="font-size:80px">{m(ing.get('pages_per_min'))}</div><div class="l">archive pages / minute ingested</div></div>
        <div class="kpi"><div class="big" style="font-size:80px">{m(inv.get('p50_s'), ' s')}</div><div class="l">median multi-hop investigation</div></div>
        <div class="kpi"><div class="big" style="font-size:80px">{audit}</div><div class="l">GPU cost of a full plant audit (49 steps, 178 docs){audit_note}</div></div>
      </div>
      <p style="margin-top:60px">Handwriting & scans read by the VLM: character error rate <b>{m(va.get('mean_cer') is not None and pct(va.get('mean_cer')) or None)}</b> ·
      {m(inv.get('calls_per_step'))} model calls per step{price}</p>{ab}{partial}"""))
    s.append(slide(f"""
      <div class="eyebrow">Evaluation · 49 steps with planted ground truth (12 fossils, 9 fences, 22 active, 6 unknown)</div>
      <h2>Missing a fence is the dangerous error.</h2>
      <table>
        <tr><th></th><th>Heuristic baseline (no LLM)</th><th>CROMO on AMD</th></tr>
        <tr><td>FENCE recall</td><td>{val(fx, 'fence_recall')}</td><td>{val(amd, 'fence_recall')}</td></tr>
        <tr><td>False-FOSSIL rate</td><td>{val(fx, 'false_fossil_rate')}</td><td>{val(amd, 'false_fossil_rate')}</td></tr>
        <tr><td>Accuracy (4 classes)</td><td>{val(fx, 'accuracy')}</td><td>{val(amd, 'accuracy')}</td></tr>
        <tr><td>Citation precision</td><td>{val(fx, 'citations', 'precision')}</td><td>{val(amd, 'citations', 'precision')}</td></tr>
        <tr><td>Prompt-injection document</td><td>{'ignored' if fx and fx['injection']['passed'] else 'pending'}</td><td>{'ignored' if amd and amd['injection']['passed'] else '<span class="pending">pending</span>'}</td></tr>
      </table>
      <p class="note" style="margin-top:28px">Synthetic archive: red herrings, contradictions, a reverted change, a reason only in a handwritten logbook. The product never reads the answer key (tested).</p>"""))
    s.append(slide(f"""
      <div class="eyebrow">Evolus Business Agents on AMD</div>
      <h2>A human approves every change - through Evolus.</h2>
      <div class="grid2">
        <img class="shot" src="{img}/trials.png">
        <div><p><b>Workflow</b>: fossil → trial plan → AI Tool brief for the engineer → approval record → decision → status back in CROMO.</p>
        <p><b>AI Tool compare</b>: what changed when a step was added. <b>Knowledge library</b>: the 178-document archive.
        {'<b>Extractor + agent</b> running on our AMD-hosted open model.' if n['agent'] else ''}</p>
        <p class="note">All driven through the Evolus REST API; created via POST /workflows.</p></div>
      </div>"""))
    s.append(slide(f"""
      <div class="eyebrow">Business value · roadmap · team</div>
      <h2>Find the waste. Keep the fences.</h2>
      <div class="grid2" style="align-items:start">
        <div><p><b>Value</b>: in our synthetic plant, {eur(n['fossil_eur'])}/yr of fossil steps found, with an audit trail - and every fence protected
        from well-meant "optimisations".</p>
        <p><b>Model</b>: per-site subscription for process industries (coatings, chemicals, food, pharma); the change-check API for MES and optimisation vendors.</p></div>
        <div><p><b>Next</b>: pilot on a real archive · veteran-interview mode for unknowns (voice on AMD) · MES connectors · cross-recipe fossil detection.</p>
        <p><b>Team</b>: solo developer, built with Claude Code. MIT licensed, open models, zero budget.</p></div>
      </div>"""))
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>CROMO slides</title>
<link rel="stylesheet" href="fonts.css"><style>{CSS}</style></head><body>{''.join(s)}</body></html>"""


def _ph(x, fmt=pct, name="") -> str:
    """A measured value, or a clearly marked placeholder that only an AMD run can fill."""
    return fmt(x) if x is not None else f"[AMD: {name}]"


def submission_blocks(n: dict) -> dict[str, str]:
    st, b, amd, fx = stack(n), n["bench"] or {}, n["amd"], n["fx"] or {}
    mo = st["models"]
    lines = [f"The AI pipeline runs on {st['where']}:"]
    if st["gemma"]:
        both = st["same"]
        lines.append("- **Gemma 4 (Google DeepMind, 26B-A4B, open weights)** "
                     + ("as both the eyes and the brain: it reads every scanned, faxed and handwritten Italian page, reasons "
                        "over the evidence and proposes verdicts" if both else "as the " + ("reasoner" if "gemma" in mo["reasoner"].lower() else "vision model"))
                     + (", and drives the Evolus agent through native tool calling;" if (n["agent"] or not st["measured"]) and not st["tf"] else ";"))
    off = lambda m: not m or m.startswith("fixture")  # noqa: E731  role not served on AMD in this run
    if not st["same"] or not st["gemma"]:
        for role in ("vision", "reasoner"):
            m = mo.get(role) or ""
            if off(m) and role == "vision":
                lines.append("- scanned pages: recorded transcriptions (no AMD vision model on this route);")
            elif not (st["gemma"] and "gemma" in m.lower()):
                lines.append(f"- {role}: {st['label'](m)};")
    lines.append("- retrieval embeddings: computed locally (no AMD embedding model on this route);" if off(mo.get("embeddings", ""))
                 else f"- {st['label'](mo.get('embeddings', ''))} for multilingual retrieval;")
    vc = n["vc"]
    if vc and vc.get("verdict"):
        lines.append(f"- a measured vision A/B on the same GPU: {vc['verdict']}")
    elif not st["measured"] or (not st["tf"] and not vc):
        lines.append("- a vision A/B against Qwen2.5-VL on the same GPU, so Gemma's reading quality is measured, not assumed "
                     "(result: [AMD: vision A/B verdict]).")
    lines[-1] = lines[-1].rstrip(";") + ("" if lines[-1].endswith(".") else ".")
    stack_md = "\n".join(lines)

    ing, inv, cost, va = b.get("ingest") or {}, b.get("investigation") or {}, b.get("cost") or {}, b.get("vision_accuracy") or {}
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
               + (f", reads scans and handwriting with a character error rate of {_ph(va.get('mean_cer'), name='CER')}" if vision_on_amd else "")
               + f" and takes {_ph(inv.get('p50_s'), str, 'median s')} s for a median multi-hop investigation.")
        if cost.get("per_plant_audit_usd") is not None:
            res += f" A full plant audit (178 documents, 49 steps) costs ${cost['per_plant_audit_usd']} of GPU time."
        elif st["tf"] and b:
            res += " (The Token Factory has no per-GPU billing, so we claim no audit cost.)"
        else:
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
    return {"AMD-STACK": stack_md, "AMD-RESULTS": res, "EVOLUS": "\n".join(ev)}


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
        subprocess.run([sys.executable, str(ROOT / "scripts" / "screenshot.py"), "http://localhost:8765/#/cover",
                        str(OUT / "cover.png"), "--size", "1600x900", "--wait", "5000"], check=True)
        print("cover:", OUT / "cover.png")
    except OSError:
        print("cover: skipped (start the app on :8765 to refresh it)")


def main():
    refresh_cover()
    n = numbers()
    update_submission(n)
    d = OUT / "slides"
    d.mkdir(parents=True, exist_ok=True)
    # self-hosted fonts (OFL) from the frontend build dependencies
    fonts = ROOT / "frontend" / "node_modules" / "@fontsource"
    css = []
    for fam, files in (("IBM Plex Sans", ["ibm-plex-sans/files/ibm-plex-sans-latin-400-normal.woff2", "ibm-plex-sans/files/ibm-plex-sans-latin-600-normal.woff2"]),):
        for i, f in enumerate(files):
            src = fonts / f
            if src.exists():
                shutil.copyfile(src, d / src.name)
                css.append(f"@font-face {{ font-family: '{fam}'; font-weight: {400 if i == 0 else 600}; src: url('{src.name}'); }}")
    fr = ROOT / "frontend" / "node_modules" / "@fontsource-variable" / "fraunces" / "files" / "fraunces-latin-wght-normal.woff2"
    if fr.exists():
        shutil.copyfile(fr, d / fr.name)
        css.append(f"@font-face {{ font-family: 'Fraunces'; font-weight: 100 900; src: url('{fr.name}'); }}")
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
