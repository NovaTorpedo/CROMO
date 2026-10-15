"""Build the synthetic Valdorso archive (reproducible, seeded).

Outputs
  archive/docs/ACC-NNNN/page-K.webp     page images (scans are degraded)
  archive/docs/ACC-NNNN/text_layer.json only for born-digital documents
  archive/catalog.csv                   records-management catalogue (no content)
  archive/plant/*.json|csv              MES / ERP exports the product may use
  fixtures/vision/<sha256>.json         recorded transcriptions of scanned pages
                                        (offline fixture mode only)
  eval/ground_truth.json                planted truth - NEVER read by the product

Usage:  python generator/build_archive.py [--seed 1995]
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from render import (PageWriter, aged_factor, degrade, fax_banner, human_date, letterhead,  # noqa: E402
                    margin_note, signature, stamp, to_rgb_webp_bytes)
from scenario_docs import DOCS, VAL  # noqa: E402
from scenario_noise import make_noise  # noqa: E402
from scenario_plant import (MATERIALS, PLANT, PLANT_PARAMETERS, PROCESSES, REVISIONS,  # noqa: E402
                            steps_at)
from scenario_truth import CHANGE_CHECKS, INJECTION_DOCS, STEPS, TRIPWIRES  # noqa: E402

ROOT = HERE.parent
PROC_TITLES = {
    "ALK": ("RECIPE CARD", "AF-12 anti-rust alkyd enamel"),
    "EPX": ("RECIPE CARD", "EF-210 epoxy floor coating - Part A"),
    "SOL": ("STANDARD OPERATING PROCEDURE", "SOP-07 Solvent cleaning of dispersers and mixing vessels"),
    "TNK": ("RECIPE CARD", "TL-5 tank sealing compound (1K PU)"),
    "QC": ("QC RELEASE PLAN", "QP-02 Batch QC release"),
}


def recipe_docs() -> list[dict]:
    out = []
    for proc, rev, date, author, note, form in REVISIONS:
        kind, name = PROC_TITLES[proc]
        body = [f"Document: {name}", f"Revision: {rev}, effective {date[8:10]}/{date[5:7]}/{date[:4]}.", "## Steps"]
        body += [f"{i + 1}. {t}" for i, t in enumerate(steps_at(proc, date))]
        body += ["## Change note", note, f"Prepared by: {author}"]
        out.append({"key": f"RCP-{proc}-{rev.replace(' ', '')}", "ref": f"{name.split()[0]} {rev}", "date": date, "form": form,
                    "title": f"{kind} - {name}", "body": body, "org": VAL, "lang": "en",
                    "stamps": ["SUPERSEDED\nARCHIVE COPY"], "note": None, "sign": author, "email": None, "fax": None,
                    "kind": "recipe (superseded)"})
    for p in PROCESSES:
        kind, name = PROC_TITLES[p["id"]]
        date = p["revision_date"]
        body = [f"Document: {name}", f"Revision: {p['revision']} (current), effective {date[8:10]}/{date[5:7]}/{date[:4]}.",
                f"Batch size: {p['batch_size']}. Equipment: {', '.join(p['equipment'])}.", "## Steps"]
        body += [f"{i + 1}. {s['instruction']}" for i, s in enumerate(p["steps"])]
        body += ["Controlled copy - the MES recipe is the master."]
        out.append({"key": f"RCP-{p['id']}-CURRENT", "ref": f"{name.split()[0]} {p['revision']}", "date": date, "form": "digital",
                    "title": f"{kind} - {name}", "body": body, "org": VAL, "lang": "en", "stamps": [], "note": None,
                    "sign": None, "email": None, "fax": None, "kind": "recipe (current)"})
    return out


def render_doc(d: dict, rng: random.Random):
    year = int(d["date"][:4])
    form = d["form"]
    pw = PageWriter(form, rng, aged_factor(year))
    lang = d.get("lang", "en")
    date_str = human_date(d["date"], lang, form)
    if form == "fax":
        fax_banner(pw, d.get("fax") or "011 555 0100", date_str)
    if form == "email":
        e = d["email"]
        pw.text(f"From: {e['from']}", kind="header", gap=0)
        pw.text(f"To: {e['to']}", kind="header", gap=0)
        if e.get("cc"):
            pw.text(f"Cc: {e['cc']}", kind="header", gap=0)
        pw.text(f"Date: {date_str}", kind="header", gap=0)
        pw.text(f"Subject: {e['subject']}", bold=True, kind="header", gap=4)
        pw.rule(gap=12)
    else:
        org = d.get("org") or VAL
        ref = d.get("ref")
        if form == "handwritten":
            letterhead(pw, "", None, None, date_str, None)
        else:
            letterhead(pw, org[0], org[1], ref, date_str if form != "fax" else None, d.get("title"))
    for para in d["body"]:
        if para.startswith("## "):
            pw.space(4)
            pw.text(para[3:], bold=True, size=(pw.style["size"] + 1), kind="header", gap=4)
        elif para.startswith("> "):
            pw.text(para[2:], indent=28, color=(70, 70, 120) if form == "email" else None, gap=8)
        else:
            pw.text(para, gap=10 if form != "handwritten" else 2)
    if d.get("sign") and form not in ("email", "handwritten"):
        pw.space(18)
        pw.ensure(80)
        if form == "digital":
            pw.text(f"Prepared by: {d['sign']}", size=16, kind="meta")
        else:
            y = pw.y
            pw.text(f"Signature: {d['sign']}", size=16, kind="meta")
            signature(pw.pages[-1], rng, d["sign"], y=y - 30)
    first = pw.pages[0]
    for s in d.get("stamps", []):
        stamp(first, rng, s, color=(176, 36, 48) if "SUPERSEDED" not in s else (40, 70, 150))
    if d.get("note"):
        margin_note(pw.pages[-1], rng, d["note"])
    images = [degrade(p, rng, form, aged_factor(year)) for p in pw.pages]
    return pw.pages, images


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=1995)
    args = ap.parse_args()
    rng = random.Random(args.seed)

    docs = DOCS + recipe_docs() + make_noise(random.Random(args.seed + 1))
    keys = [d["key"] for d in docs]
    dupes = {k for k in keys if keys.count(k) > 1}
    assert not dupes, f"duplicate doc keys: {dupes}"
    missing = {k for s in STEPS.values() for k in s["key"] + s["also"]} - set(keys)
    assert not missing, f"ground truth references unknown docs: {missing}"

    order = list(range(len(docs)))
    rng.shuffle(order)

    out_docs = ROOT / "archive" / "docs"
    fix_dir = ROOT / "fixtures" / "vision"
    for p in (out_docs, fix_dir):
        if p.exists():
            shutil.rmtree(p)
        p.mkdir(parents=True)
    (ROOT / "archive" / "plant").mkdir(parents=True, exist_ok=True)
    (ROOT / "eval").mkdir(exist_ok=True)

    key_to_acc, catalog = {}, []
    for n, idx in enumerate(order, start=1):
        d = docs[idx]
        acc = f"ACC-{n:04d}"
        key_to_acc[d["key"]] = acc
        drng = random.Random(f"{args.seed}-{d['key']}")
        pages, images = render_doc(d, drng)
        ddir = out_docs / acc
        ddir.mkdir()
        digital = d["form"] in ("digital", "email")
        layer = {"pages": []}
        for k, (pg, img) in enumerate(zip(pages, images), start=1):
            data = to_rgb_webp_bytes(img, quality=72 if digital else 60)
            (ddir / f"page-{k}.webp").write_bytes(data)
            lines = [{"text": ln.text, "bbox": list(ln.bbox)} for ln in pg.lines]
            if digital:
                layer["pages"].append({"page": k, "width": img.width, "height": img.height, "lines": lines})
            else:
                sha = hashlib.sha256(data).hexdigest()
                (fix_dir / f"{sha}.json").write_text(json.dumps({
                    "note": "Recorded transcription for OFFLINE FIXTURE MODE (generator output, not a model reading).",
                    "width": img.width, "height": img.height, "lines": lines}, ensure_ascii=False), encoding="utf-8")
        if digital:
            (ddir / "text_layer.json").write_text(json.dumps(layer, ensure_ascii=False, indent=0), encoding="utf-8")
        catalog.append({"accession": acc, "box": f"BOX-{(int(d['date'][:4]) - 1990) // 3 + 1:02d}",
                        "pages": len(pages), "text_layer": "yes" if digital else "no",
                        "scanned": "born-digital" if digital else f"scan batch {rng.choice(['2019-03', '2019-04', '2024-11'])}"})

    with open(ROOT / "archive" / "catalog.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(catalog[0].keys()))
        w.writeheader()
        w.writerows(sorted(catalog, key=lambda r: r["accession"]))

    # ---- plant data (legitimate product inputs) ------------------------------
    plant = ROOT / "archive" / "plant"
    mes = {"export": "MES recipe export (synthetic)", "exported_at": "2026-09-30", "plant": PLANT,
           "processes": [{k: v for k, v in p.items()} for p in PROCESSES]}
    (plant / "mes_recipes_current.json").write_text(json.dumps(mes, ensure_ascii=False, indent=1), encoding="utf-8")
    (plant / "plant_parameters.json").write_text(json.dumps(PLANT_PARAMETERS, indent=1), encoding="utf-8")
    with open(plant / "material_master.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["code", "name", "unit", "price_eur", "current_supplier", "aliases"])
        for code, name, unit, price, sup, aliases in MATERIALS:
            w.writerow([code, name, unit, price, sup, "|".join(aliases)])

    # ---- ground truth (eval only) --------------------------------------------
    def accs(ks):
        return [key_to_acc[k] for k in ks]

    gt = {
        "_warning": "Evaluation ground truth. The CROMO pipeline must never read this file.",
        "dataset": f"Valdorso synthetic archive (seed {args.seed})",
        "documents": {k: {"accession": v, "kind": next(d.get('kind') for d in docs if d['key'] == k),
                          "date": next(d['date'] for d in docs if d['key'] == k)} for k, v in key_to_acc.items()},
        "steps": {sid: {**t, "key_accessions": accs(t["key"]), "also_accessions": accs(t["also"])} for sid, t in STEPS.items()},
        "injection_documents": accs(INJECTION_DOCS),
        "tripwires": TRIPWIRES,
        "change_checks": CHANGE_CHECKS,
    }
    (ROOT / "eval" / "ground_truth.json").write_text(json.dumps(gt, ensure_ascii=False, indent=1), encoding="utf-8")

    labels = [t["label"] for t in STEPS.values()]
    print(f"documents: {len(docs)}  pages: {sum(c['pages'] for c in catalog)}  "
          f"digital: {sum(c['text_layer'] == 'yes' for c in catalog)}  scanned: {sum(c['text_layer'] == 'no' for c in catalog)}")
    print("labels:", {lab: labels.count(lab) for lab in sorted(set(labels))})


if __name__ == "__main__":
    main()
