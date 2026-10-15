"""Routine, mostly irrelevant archive documents (SYNTHETIC). Seeded.

Real archives are dominated by paperwork that has nothing to do with any given
question. Some of these are deliberate red herrings (e.g. a hot-box thermostat
repair shows the hot box is in use, not why it exists; invoices from a supplier
that still delivers a *different* material).
"""

import random

from scenario_docs import VAL

SUPPLIER_ORGS = {
    "Resine Altamira S.p.A.": ("RESINE ALTAMIRA S.p.A.", "Resine alchidiche ed epossidiche"),
    "Fosfazinco Nord S.p.A.": ("FOSFAZINCO NORD S.p.A.", "Pigmenti anticorrosivi"),
    "Chimica Ondina S.n.c.": ("CHIMICA ONDINA S.n.c.", "Additivi e prodotti chimici"),
    "Solventi Garbagna S.r.l.": ("SOLVENTI GARBAGNA S.r.l.", "Solventi industriali"),
    "Kessler-Ondra Harze GmbH": ("KESSLER-ONDRA HARZE GmbH", "Epoxidharze"),
    "Quarzi Monterosso S.p.A.": ("QUARZI MONTEROSSO S.p.A.", "Cariche minerali"),
    "Nordpol Chemicals AB": ("NORDPOL CHEMICALS AB", "Polyols"),
    "Isocianati Varesotti S.p.A.": ("ISOCIANATI VARESOTTI S.p.A.", "Isocianati e prepolimeri"),
    "Imballaggi Corvino S.r.l.": ("IMBALLAGGI CORVINO S.r.l.", "Imballaggi metallici"),
    "Silicati Brenta S.r.l.": ("SILICATI BRENTA S.r.l.", "Cariche e bentoniti"),
    "Cromopigmenti Lazzeretti S.r.l.": ("CROMOPIGMENTI LAZZERETTI S.r.l.", "Pigmenti inorganici"),
    "Polioli Sereni S.p.A.": ("POLIOLI SERENI S.p.A.", "Polioli"),
}

# (supplier, material, unit, unit price, year range)
INVOICE_LINES = [
    ("Resine Altamira S.p.A.", "Alkyd resin AL-60, drums 200 kg", "kg", 2.1, (2003, 2025)),
    ("Resine Altamira S.p.A.", "Epoxy resin ALTAREP E-19, drums", "kg", 3.4, (1998, 2011)),
    ("Fosfazinco Nord S.p.A.", "Zinc phosphate ZP-40, bags 25 kg", "kg", 3.2, (2007, 2025)),
    ("Chimica Ondina S.n.c.", "Ammonium chloride technical, bags 25 kg", "kg", 1.35, (1997, 2025)),
    ("Chimica Ondina S.n.c.", "Soy lecithin, pails 20 kg", "kg", 4.2, (1996, 2025)),
    ("Chimica Ondina S.n.c.", "DBTDL catalyst, cans 25 kg", "kg", 18.0, (2000, 2025)),
    ("Solventi Garbagna S.r.l.", "Acetone, bulk delivery", "l", 1.05, (1996, 2025)),
    ("Solventi Garbagna S.r.l.", "White spirit D40, bulk", "l", 1.1, (1996, 2025)),
    ("Solventi Garbagna S.r.l.", "Xylene, drums 200 L", "l", 1.6, (1996, 2025)),
    ("Kessler-Ondra Harze GmbH", "KO-Epox 410 LC, drums 220 kg", "kg", 3.9, (2012, 2025)),
    ("Quarzi Monterosso S.p.A.", "Quartz flour 0.1 mm, big-bag 1 t", "kg", 0.32, (2010, 2025)),
    ("Nordpol Chemicals AB", "Polyol NP-310 Dry, tank truck", "kg", 2.7, (2016, 2025)),
    ("Isocianati Varesotti S.p.A.", "MDI prepolymer, IBC", "kg", 3.5, (1999, 2025)),
    ("Imballaggi Corvino S.r.l.", "5 L tinplate cans", "pc", 1.1, (2017, 2025)),
    ("Silicati Brenta S.r.l.", "Bentonite Bentagel, bags 25 kg", "kg", 2.4, (1998, 2025)),
    ("Polioli Sereni S.p.A.", "Polyol PS-400, drums", "kg", 2.2, (1997, 2015)),
    ("Cromopigmenti Lazzeretti S.r.l.", "Basic lead chromate CL-77, bags 25 kg", "kg", 4.1, (1994, 2006)),
]


def _form_for(year: int, rng: random.Random) -> str:
    if year < 2003:
        return rng.choice(["typed", "scan", "fax"]) if year < 1999 else rng.choice(["scan", "fax", "scan"])
    return "digital" if rng.random() < 0.8 else "scan"


def make_noise(rng: random.Random) -> list[dict]:
    docs: list[dict] = []

    def add(key, date, form, title, body, **kw):
        d = {"key": key, "ref": kw.pop("ref", key), "date": date, "form": form, "title": title, "body": body,
             "org": kw.pop("org", VAL), "lang": kw.pop("lang", "en"), "stamps": kw.pop("stamps", []),
             "note": kw.pop("note", None), "sign": kw.pop("sign", None), "email": kw.pop("email", None),
             "fax": kw.pop("fax", None), "kind": kw.pop("kind", None), "noise": True}
        docs.append(d)

    # --- invoices (20) -------------------------------------------------------
    picks = rng.sample(INVOICE_LINES, len(INVOICE_LINES)) + rng.sample(INVOICE_LINES, 3)
    for i, (sup, mat, unit, price, (y0, y1)) in enumerate(picks):
        y = rng.randint(y0, y1)
        m, d = rng.randint(1, 12), rng.randint(1, 28)
        qty = rng.choice([400, 800, 1000, 2000, 5000, 12000, 24000]) if unit != "pc" else rng.choice([5000, 10000, 20000])
        p = price * (0.62 if y < 2002 else 1.0) * rng.uniform(0.9, 1.08)
        cur = "LIT" if y < 2002 else "EUR"
        amount = qty * p * (1936.27 if cur == "LIT" else 1)
        num = f"{rng.randint(100, 9999)}/{str(y)[2:]}"
        form = _form_for(y, rng)
        add(f"INV-{y}-{i:02d}", f"{y}-{m:02d}-{d:02d}", form, f"FATTURA / INVOICE n. {num}", [
            "Bill to: Valdorso Coatings S.p.A., Via delle Fornaci 7, Borgo Valdorso (TO).",
            f"Item: {mat}. Quantity: {qty:,} {unit}. Unit price: {p * (1936.27 if cur == 'LIT' else 1):,.2f} {cur}.",
            f"Total excl. VAT: {amount:,.0f} {cur}. Payment: 60 days end of month.",
            f"Delivery note: DDT {rng.randint(1000, 9999)} of {d:02d}/{m:02d}/{y}.",
        ], ref=None, org=SUPPLIER_ORGS[sup], kind="invoice")

    # --- maintenance logs (8) -------------------------------------------------
    equipment = [
        ("compressor C-1", ["oil and filter changed", "air leak on outlet fixed", "dryer cartridge replaced", "annual inspection OK"]),
        ("boiler B-1", ["burner nozzle cleaned", "flue gas analysis within limits", "safety valve tested"]),
        ("forklift FK-2", ["battery replaced", "brake pads replaced", "mast chain lubricated"]),
        ("pump P-3", ["gland packing replaced", "impeller inspected", "coupling realigned"]),
        ("hot box HB-1", ["thermostat replaced", "door seal replaced", "heating element 3 replaced"]),
        ("filling line FL-2", ["capping head adjusted", "conveyor belt tensioned", "scale checked"]),
        ("disperser D-3", ["gearbox overhaul", "shaft seal replaced", "V-belts replaced"]),
        ("cooling tower CT-1", ["legionella treatment", "fan bearing greased", "basin cleaned"]),
    ]
    for i, (eq, acts) in enumerate(equipment):
        y = rng.randint(1996, 2025)
        lines = []
        for _ in range(rng.randint(3, 5)):
            yy = min(2025, y + rng.randint(0, 2))
            lines.append(f"{rng.randint(1, 28):02d}/{rng.randint(1, 12):02d}/{yy}  {rng.choice(acts).capitalize()}. ({rng.choice([1, 1.5, 2, 3, 4])} h)")
        lines.sort(key=lambda s: (s[6:10], s[3:5], s[0:2]))
        add(f"ML-NOISE-{i}", f"{y}-12-15", _form_for(y, rng), f"MAINTENANCE LOG - {eq.upper()} (extract)", lines,
            ref=None, kind="maintenance log")

    # --- calibration certificates (5) -----------------------------------------
    for i, (inst, val) in enumerate([("Brookfield viscometer DV-2", "deviation 0.8 % - within tolerance"),
                                     ("Hegman gauge HG-04", "flatness and depth OK"),
                                     ("Portable gas detector GD-3 (O2/LEL)", "bump test passed; span 50 % LEL OK"),
                                     ("Gloss meter GM-60", "standard tile 93.2 GU vs 93.0 nominal"),
                                     ("Karl Fischer titrator KF-1", "water standard 1.00 mg: 1.01 mg")]):
        y = rng.randint(2010, 2025)
        add(f"CAL-{y}-{i}", f"{y}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}", "digital",
            f"Calibration certificate - {inst}", [
                f"Instrument: {inst}. Result: {val}.", "Next calibration due in 12 months.",
                "Laboratorio Metrologico Canavese (accredited).",
            ], ref=None, org=("LABORATORIO METROLOGICO CANAVESE", "Calibration certificate"), kind="calibration certificate")

    # --- meeting minutes (7) ---------------------------------------------------
    topics = [
        ["Safety training plan: fire drills in March and October.", "New PPE supplier for gloves.", "Canteen menu survey."],
        ["ISO 9001 surveillance audit: two minor findings on document control.", "Shelving in the QC lab.", "Christmas shutdown 23/12-07/01."],
        ["Energy: photovoltaic roof proposal (450 kWp) to be evaluated.", "Compressed air leak survey results: 14 leaks fixed.",
         "Night shift staffing."],
        ["Customer visit from an agricultural OEM next week; route through warehouse M5.", "Forklift traffic plan updated."],
        ["Waste solvent contractor contract renewed for 3 years.", "Spill kit inspection monthly.", "Parking lot lighting."],
        ["Budget 2020: new gas detectors, replacement of FK-2 forklift.", "Recruitment of a QC technician."],
        ["Ergonomics: lifting aids for 25 kg bags at D-2.", "Ventilation of the solvent room: annual check done."],
    ]
    for i, t in enumerate(topics):
        y = rng.randint(1998, 2025)
        form = "digital" if y >= 2003 else "typed"
        add(f"MM-NOISE-{i}", f"{y}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}", form,
            f"Minutes - plant meeting ({y})", [f"{k + 1}. {x}" for k, x in enumerate(t)], ref=None, kind="meeting minutes")

    # --- waste manifests (4) ----------------------------------------------------
    for i in range(4):
        y = rng.randint(2004, 2025)
        add(f"WM-{y}-{i}", f"{y}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}", "digital",
            f"Waste transport form n. {rng.randint(10000, 99999)}", [
                "Producer: Valdorso Coatings S.p.A. - Borgo Valdorso.",
                f"Waste: spent non-halogenated solvents (EWC 07 01 04*). Quantity: {rng.randint(8, 22) * 1000:,} kg.",
                "Carrier: Ecotrasporti Dora. Destination: solvent recovery plant.",
            ], ref=None, kind="waste manifest")

    # --- training records (3) ----------------------------------------------------
    for i, course in enumerate(["Forklift operation refresher", "First aid level B", "Handling of isocyanates"]):
        y = rng.randint(2008, 2025)
        add(f"TR-{y}-{i}", f"{y}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}", "digital",
            f"Training record - {course}", [
                f"Course: {course}. Duration: {rng.choice([4, 8, 12])} h. Participants: {rng.randint(6, 18)}.",
                "Trainer: external. Attendance sheet and test results filed with HR.",
            ], ref=None, kind="training record")

    # --- misc emails (4) ---------------------------------------------------------
    misc = [
        ("IT department", "All staff", "Password change reminder", ["Please change your MES password before Friday."]),
        ("Marco Viale", "Department heads", "Visit of the fire brigade", ["Inspection on Tuesday 10:00, solvent room and warehouse M5."]),
        ("HR", "All staff", "Summer timetable", ["From 1 July the canteen opens at 11:45."]),
        ("Giulia Testa (Purchasing)", "Davide Morra", "Acetone price increase",
         ["Solventi Garbagna announces +6 % on acetone from next quarter. Please check consumption forecasts."]),
    ]
    for i, (frm, to, subj, body) in enumerate(misc):
        y = rng.randint(2011, 2025)
        add(f"EMAIL-NOISE-{i}", f"{y}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}", "email", None, body, ref=None,
            org=None, email={"from": frm, "to": to, "cc": None, "subject": subj}, kind="email")

    return docs
