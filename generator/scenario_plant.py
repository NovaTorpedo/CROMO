"""Fictional plant master data: Valdorso Coatings S.p.A. (SYNTHETIC).

Everything here is invented for the CROMO demo. The company, people, suppliers,
customers, regulations and agencies are fictional; any resemblance to real
entities is coincidental.

This module produces the *plant data* the product legitimately has access to
(MES recipe export, ERP price list, material master, plant parameters) plus the
recipe revision history that is rendered into archive documents.
"""

PLANT = {
    "name": "Valdorso Coatings S.p.A.",
    "site": "Borgo Valdorso (TO), Italy",
    "synthetic": True,
    "description": "Mid-sized industrial coatings plant (fictional). Primers, enamels, epoxy floor coatings, PU sealants.",
}

PLANT_PARAMETERS = {
    "currency": "EUR",
    "labor_rate_eur_per_h": 38.0,
    "energy_price_eur_per_kwh": 0.21,
    "solvent_disposal_eur_per_l": 0.55,
    "disperser_occupancy_eur_per_h": 14.0,
    "holding_tank_eur_per_h": 1.8,
    "nitrogen_eur_per_m3": 0.42,
    "volumes": {
        "ALK": {"basis": "batch", "per_year": 1850, "label": "AF-12 batches/yr"},
        "EPX": {"basis": "batch", "per_year": 1150, "label": "EF-210 A batches/yr"},
        "SOL": {"basis": "cleaning", "per_year": 3900, "label": "vessel cleanings/yr"},
        "TNK": {"basis": "batch", "per_year": 620, "label": "TL-5 batches/yr"},
        "QC": {"basis": "release", "per_year": 3620, "label": "batch releases/yr"},
        "winter_fraction": 0.42,
        "pigment_lots_per_year": 950,
        "pigment_additions_per_year": 3000,
    },
    "source": "ERP controlling export 2026-09 (synthetic)",
}

# code, name, unit, price EUR/unit, current supplier, aliases
MATERIALS = [
    ("RM-101", "Long-oil alkyd resin AL-60", "kg", 2.10, "Resine Altamira S.p.A.", ["alkyd resin", "AL-60"]),
    ("RM-110", "Zinc phosphate anti-corrosive pigment ZP-40", "kg", 3.20, "Fosfazinco Nord S.p.A.", ["zinc phosphate", "ZP-40"]),
    ("RM-118", "Ammonium chloride, technical", "kg", 1.35, "Chimica Ondina S.n.c.", ["ammonium chloride", "NH4Cl", "cloruro d'ammonio"]),
    ("RM-120", "Bentonite anti-settling agent Bentagel", "kg", 2.40, "Silicati Brenta S.r.l.", ["bentonite", "anti-settling agent"]),
    ("RM-131", "White spirit D40 (flash point 39 C)", "l", 1.10, "Solventi Garbagna S.r.l.", ["white spirit", "mineral spirits"]),
    ("RM-140", "Drier pack Co/Zr", "kg", 9.80, "Chimica Ondina S.n.c.", ["drier", "cobalt drier"]),
    ("RM-141", "MEKO anti-skinning agent", "kg", 7.50, "Chimica Ondina S.n.c.", ["MEKO", "anti-skin"]),
    ("RM-150", "Soy lecithin", "kg", 4.20, "Chimica Ondina S.n.c.", ["lecithin", "lecitina"]),
    ("RM-201", "Liquid epoxy resin KO-Epox 410 LC", "kg", 3.90, "Kessler-Ondra Harze GmbH", ["epoxy resin", "KO-410", "KO-Epox 410 LC"]),
    ("RM-205", "Reactive diluent C12-C14 glycidyl ether", "kg", 4.60, "Kessler-Ondra Harze GmbH", ["reactive diluent", "glycidyl ether"]),
    ("RM-210", "Quartz flour 0.1 mm", "kg", 0.32, "Quarzi Monterosso S.p.A.", ["quartz flour", "silica flour"]),
    ("RM-212", "Micro-silica", "kg", 1.80, "Quarzi Monterosso S.p.A.", ["micro-silica", "microsilica"]),
    ("RM-220", "Silicone defoamer", "kg", 12.00, "Chimica Ondina S.n.c.", ["defoamer"]),
    ("RM-301", "Acetone", "l", 1.05, "Solventi Garbagna S.r.l.", ["acetone"]),
    ("RM-305", "Xylene", "l", 1.60, "Solventi Garbagna S.r.l.", ["xylene", "xilene"]),
    ("RM-401", "Polyether polyol NP-310 Dry", "kg", 2.70, "Nordpol Chemicals AB", ["polyol", "NP-310"]),
    ("RM-405", "Molecular sieve 3A", "kg", 6.80, "Essiccanti Marelli S.r.l.", ["molecular sieve", "setacci molecolari"]),
    ("RM-410", "MDI prepolymer", "kg", 3.50, "Isocianati Varesotti S.p.A.", ["isocyanate", "MDI prepolymer", "MDI"]),
    ("RM-415", "DBTDL catalyst (dibutyltin dilaurate)", "kg", 18.00, "Chimica Ondina S.n.c.", ["DBTDL", "organotin catalyst", "tin catalyst"]),
    ("UT-01", "Nitrogen (bulk)", "m3", 0.42, "Gas Tecnici Valdorso", ["nitrogen", "N2", "azoto"]),
    ("PK-20", "20 kg steel pail", "pc", 2.60, "Imballaggi Corvino S.r.l.", ["pail", "secchio"]),
    ("PK-05", "5 L tinplate can", "pc", 1.10, "Imballaggi Corvino S.r.l.", ["can", "latta"]),
]


def S(sid, instruction, *, mats=(), labor=0, energy=0.0, occ_min=0, hold_h=0.0, n2=0.0, solvent_l=0.0, basis=None):
    return {
        "id": sid,
        "instruction": instruction,
        "materials": [{"code": c, "qty": q} for c, q in mats],
        "labor_min": labor,
        "energy_kwh": energy,
        "disperser_min": occ_min,
        "holding_h": hold_h,
        "nitrogen_m3": n2,
        "waste_solvent_l": solvent_l,
        "runs_basis": basis,  # None = process volume
    }


PROCESSES = [
    {
        "id": "ALK", "code": "AF-12", "name": "AF-12 anti-rust alkyd enamel", "kind": "batch recipe",
        "revision": "Rev 14", "revision_date": "2023-05-10", "batch_size": "2,000 kg", "equipment": ["D-2", "holding tanks HT-1..4", "FL-2"],
        "steps": [
            S("ALK-01", "Charge 1,040 kg long-oil alkyd resin AL-60 (RM-101) into disperser D-2; start agitator at 300 rpm.", mats=[("RM-101", 1040)], labor=15),
            S("ALK-02", "Add 360 kg zinc phosphate anti-corrosive pigment ZP-40 (RM-110) over 10 min.", mats=[("RM-110", 360)], labor=12),
            S("ALK-03", "Add 0.4 kg soy lecithin (RM-150) together with the pigment.", mats=[("RM-150", 0.4)], labor=3),
            S("ALK-04", "Add 1.6 kg ammonium chloride (RM-118) pre-dissolved in 4 L water; stir 10 min.", mats=[("RM-118", 1.6)], labor=10),
            S("ALK-05", "Winter dose: from 1 November to 31 March add 3 kg bentonite anti-settling agent (RM-120).", mats=[("RM-120", 3)], labor=5, basis="winter"),
            S("ALK-06", "Disperse at 1,400 rpm until fineness of grind is at least 6 Hegman (approx. 40 min).", labor=10, energy=30),
            S("ALK-07", "Cool the batch below 40 °C before solvent letdown and record the temperature (hold up to 30 min).", labor=3, occ_min=30),
            S("ALK-08", "Let down with 320 kg white spirit D40 (RM-131) at 600 rpm.", mats=[("RM-131", 400)], labor=10),
            S("ALK-09", "Add 9 kg Co/Zr drier pack (RM-140) and 4 kg MEKO anti-skinning agent (RM-141).", mats=[("RM-140", 9), ("RM-141", 4)], labor=6),
            S("ALK-10", "Transfer to holding tank and rest the batch 12 h before QC sampling.", labor=5, hold_h=12),
            S("ALK-11", "Filter through 50 µm bag filter and fill 20 L tins on line FL-2.", labor=45),
        ],
    },
    {
        "id": "EPX", "code": "EF-210 A", "name": "EF-210 epoxy floor coating, Part A", "kind": "batch recipe",
        "revision": "Rev 9", "revision_date": "2022-01-20", "batch_size": "1,600 kg", "equipment": ["D-1", "HB-1", "VS-1", "FL-2"],
        "steps": [
            S("EPX-01", "Run disperser D-1 empty for 5 min before charging (warm-up).", labor=5, energy=3.75, occ_min=5),
            S("EPX-02", "Pre-heat epoxy resin drums in hot box HB-1 at 40 °C for 12 h before use.", labor=15, energy=36),
            S("EPX-03", "Charge 860 kg liquid epoxy resin KO-Epox 410 LC (RM-201).", mats=[("RM-201", 860)], labor=12),
            S("EPX-04", "Add 80 kg reactive diluent (RM-205); mix 10 min.", mats=[("RM-205", 80)], labor=5),
            S("EPX-05", "Wait 20 min after the diluent addition before taking the viscosity sample.", occ_min=20),
            S("EPX-06", "Sieve quartz flour through the 1 mm vibrating screen VS-1 before charging.", labor=15, energy=1.5),
            S("EPX-07", "Add 500 kg quartz flour (RM-210) and 40 kg micro-silica (RM-212) under vacuum (-0.8 bar).", mats=[("RM-210", 500), ("RM-212", 40)], labor=10, energy=8, occ_min=25),
            S("EPX-08", "Add 4.8 kg silicone defoamer (RM-220).", mats=[("RM-220", 4.8)], labor=3),
            S("EPX-09", "Sample and test epoxy equivalent weight (EEW) against specification 190-210 g/eq.", labor=20),
            S("EPX-10", "Flush each 20 kg pail with nitrogen (approx. 0.06 m³ per pail) before filling.", labor=10, n2=2.4),
            S("EPX-11", "Fill 20 kg pails on line FL-2, close and label.", labor=40),
            S("EPX-12", "Store filled pails upside down for 24 h before palletising.", labor=10),
        ],
    },
    {
        "id": "SOL", "code": "SOP-07", "name": "SOP-07 solvent cleaning of dispersers and mixing vessels", "kind": "standard operating procedure",
        "revision": "Rev 8", "revision_date": "2021-03-01", "batch_size": "per cleaning", "equipment": ["D-1..D-4", "T-1..T-6", "solvent station"],
        "steps": [
            S("SOL-01", "Drain residual product into the recovery drum.", labor=6),
            S("SOL-02", "Bond and earth the vessel and the solvent drum before any solvent transfer.", labor=3),
            S("SOL-03", "First rinse: circulate 40 L acetone (RM-301) for 10 min; drain to waste solvent.", mats=[("RM-301", 40)], labor=12, solvent_l=40),
            S("SOL-04", "Second rinse with 20 L fresh acetone (RM-301); drain to waste solvent.", mats=[("RM-301", 20)], labor=8, solvent_l=20),
            S("SOL-05", "Wipe agitator shaft and blades with a xylene-soaked rag (approx. 1 L xylene, RM-305).", mats=[("RM-305", 1)], labor=6, solvent_l=1),
            S("SOL-06", "Before any vessel entry: force-ventilate 15 min and check O₂ and LEL with the gas detector.", labor=4),
            S("SOL-07", "Leave the vessel lid open overnight after cleaning.", labor=1),
            S("SOL-08", "Wait at least 60 min after cleaning before charging the next batch.", occ_min=60),
            S("SOL-09", "Record the cleaning in the vessel logbook and sign.", labor=2),
        ],
    },
    {
        "id": "TNK", "code": "TL-5", "name": "TL-5 tank sealing compound (1K moisture-cure polyurethane)", "kind": "batch recipe",
        "revision": "Rev 8", "revision_date": "2021-02-15", "batch_size": "1,200 kg", "equipment": ["VD-1", "D-4", "MS-1", "OV-1"],
        "steps": [
            S("TNK-01", "Charge 900 kg polyether polyol NP-310 Dry (RM-401) and dry under vacuum at 90 °C in VD-1 until water < 0.05 %.", mats=[("RM-401", 900)], labor=15, energy=60),
            S("TNK-02", "Add 2 kg molecular sieve 3A (RM-405).", mats=[("RM-405", 2)], labor=5),
            S("TNK-03", "Establish a nitrogen blanket on D-4 before the isocyanate addition.", labor=3, n2=4),
            S("TNK-04", "Add 280 kg MDI prepolymer (RM-410) at max. 2 kg/min.", mats=[("RM-410", 280)], labor=10),
            S("TNK-05", "Add 0.6 kg DBTDL catalyst (RM-415).", mats=[("RM-415", 0.6)], labor=3),
            S("TNK-06", "Hold at 60 °C for 45 min under agitation.", energy=10, occ_min=45),
            S("TNK-07", "Pass the product through magnetic separator MS-1 before canning.", labor=8),
            S("TNK-08", "Pre-dry empty 5 L cans in oven OV-1 at 60 °C for 2 h.", labor=15, energy=44),
            S("TNK-09", "Fill 5 L cans under dry nitrogen and seal.", labor=40, n2=1.5),
        ],
    },
    {
        "id": "QC", "code": "QP-02", "name": "QP-02 batch QC release plan", "kind": "quality control plan",
        "revision": "Rev 6", "revision_date": "2021-06-07", "batch_size": "per release", "equipment": ["QC laboratory", "XRF-01", "SC-2B"],
        "steps": [
            S("QC-01", "Viscosity: Ford cup No. 4 (AF-12) or Brookfield (EF-210, TL-5) against product specification.", labor=8),
            S("QC-02", "Fineness of grind (Hegman gauge) on AF-12 and EF-210.", labor=5),
            S("QC-03", "Chloride content of every AF-12 batch (limit 400 ppm).", labor=20, basis="ALK"),
            S("QC-04", "XRF lead screening of every incoming pigment lot.", labor=15, basis="pigment_lots"),
            S("QC-05", "Retain a 0.5 L sample of every batch for 5 years.", labor=3),
            S("QC-06", "Re-weigh every pigment addition on bench scale SC-2B and countersign.", labor=6, basis="pigment_additions"),
            S("QC-07", "Gloss at 60° on drawdown (AF-12).", labor=6, basis="ALK"),
            S("QC-08", "Odour check of every batch by the QC technician.", labor=2),
        ],
    },
]

# Short step names as shown in the MES (operator-facing labels)
STEP_NAMES = {
    "ALK-01": "Alkyd resin charge", "ALK-02": "Zinc phosphate pigment", "ALK-03": "Soy lecithin",
    "ALK-04": "Ammonium chloride", "ALK-05": "Winter bentonite dose", "ALK-06": "Disperse to 6 Hegman",
    "ALK-07": "Cool below 40 °C", "ALK-08": "White spirit letdown", "ALK-09": "Driers and anti-skin",
    "ALK-10": "12-hour rest", "ALK-11": "Filter and fill",
    "EPX-01": "Disperser warm-up", "EPX-02": "Hot-box pre-heat", "EPX-03": "Epoxy resin charge",
    "EPX-04": "Reactive diluent", "EPX-05": "20-minute wait", "EPX-06": "Sieve quartz flour",
    "EPX-07": "Fillers under vacuum", "EPX-08": "Silicone defoamer", "EPX-09": "EEW test",
    "EPX-10": "Nitrogen-flush pails", "EPX-11": "Fill and label", "EPX-12": "Pails upside down",
    "SOL-01": "Drain residue", "SOL-02": "Bond and earth", "SOL-03": "First acetone rinse",
    "SOL-04": "Second acetone rinse", "SOL-05": "Xylene wipe", "SOL-06": "Ventilate before entry",
    "SOL-07": "Lid open overnight", "SOL-08": "60-minute wait", "SOL-09": "Cleaning log",
    "TNK-01": "Vacuum-dry polyol", "TNK-02": "Molecular sieve", "TNK-03": "Nitrogen blanket",
    "TNK-04": "Isocyanate addition", "TNK-05": "Tin catalyst", "TNK-06": "45-minute hold",
    "TNK-07": "Magnetic separator", "TNK-08": "Oven-dry cans", "TNK-09": "Can under nitrogen",
    "QC-01": "Viscosity", "QC-02": "Fineness of grind", "QC-03": "Chloride test", "QC-04": "XRF lead screening",
    "QC-05": "Retain samples 5 yrs", "QC-06": "Re-weigh pigments", "QC-07": "Gloss 60°", "QC-08": "Odour check",
}
PROCESS_SHORT = {"ALK": "Anti-rust enamel", "EPX": "Epoxy floor coating", "SOL": "Solvent cleaning",
                 "TNK": "Tank sealant", "QC": "QC release"}
for _p in PROCESSES:
    _p["short"] = PROCESS_SHORT[_p["id"]]
    for _s in _p["steps"]:
        _s["name"] = STEP_NAMES[_s["id"]]

# ---------------------------------------------------------------------------
# Recipe revision history (rendered as superseded recipe documents).
# Each variant: (effective ISO date, text as written at that time)
# ---------------------------------------------------------------------------
VARIANTS = {
    # AF-12
    "ALK-01": [("1994-03-15", "Charge 520 kg long-oil alkyd resin AL-60 (Resine Altamira) into disperser D-2; agitator 300 rpm.")],
    "ALK-02": [("1994-03-15", "Add 170 kg basic lead chromate pigment CL-77 (Cromopigmenti Lazzeretti)."),
               ("2007-02-19", "Add 180 kg zinc phosphate pigment ZP-40 (Fosfazinco Nord).")],
    "ALK-03": [("1994-03-15", "Add 0.2 kg soy lecithin with the pigment.")],
    "ALK-04": [("1996-01-22", "Add 0.8 kg ammonium chloride per 1000 kg batch, dissolved in 2 L water; stir 10 min.")],
    "ALK-05": [("1998-10-05", "1 Nov - 31 Mar: add 1.5 kg bentonite anti-settling agent (winter dose).")],
    "ALK-06": [("1994-03-15", "Disperse at 1,400 rpm to fineness 6 Hegman minimum.")],
    "ALK-07": [("2001-09-12", "Cool batch below 40 °C before letdown. Record temperature on batch sheet.")],
    "ALK-08": [("1994-03-15", "Let down with 160 kg white spirit.")],
    "ALK-09": [("1994-03-15", "Add 4.5 kg cobalt drier flakes dissolved in xylene and 2 kg MEKO."),
               ("2008-09-30", "Add 4.5 kg Co/Zr liquid drier pack and 2 kg MEKO.")],
    "ALK-10": [("1996-01-22", "Rest batch 12 h in holding tank before QC sample.")],
    "ALK-11": [("1994-03-15", "Filter through 80 µm sieve and fill 20 L tins."),
               ("2004-06-01", "Filter through 50 µm bag filter and fill 20 L tins on FL-2.")],
    # EF-210 A
    "EPX-01": [("1997-04-10", "Run D-1 empty 5 min before charging (see WI-1997-02).")],
    "EPX-02": [("1999-02-08", "Pre-heat all epoxy resin drums in hot box HB-1, 40 °C, 12 h.")],
    "EPX-03": [("1997-04-10", "Charge 430 kg liquid epoxy resin ALTAREP E-19 (Resine Altamira)."),
               ("2012-05-14", "Charge 430 kg liquid epoxy resin KO-Epox 410 LC (Kessler-Ondra).")],
    "EPX-04": [("1997-04-10", "Add 40 kg reactive diluent; mix 10 min.")],
    "EPX-05": [("2001-04-23", "Wait 20 min after diluent before viscosity sample.")],
    "EPX-06": [("2003-11-17", "Sieve quartz flour on 1 mm screen before charging.")],
    "EPX-07": [("1997-04-10", "Add 250 kg quartz flour and 20 kg micro-silica."),
               ("2004-09-06", "Add 250 kg quartz flour and 20 kg micro-silica under vacuum (-0.8 bar).")],
    "EPX-08": [("1997-04-10", "Add 2.4 kg silicone defoamer.")],
    "EPX-09": [("1997-04-10", "Sample; EEW 190-210 g/eq.")],
    "EPX-10": [("2005-10-03", "Flush every pail with nitrogen before filling (FL-2).")],
    "EPX-11": [("1997-04-10", "Fill 20 kg pails on FL-2, close and label.")],
    "EPX-12": [("2005-10-03", "Store filled pails upside down 24 h (FT).")],
    # SOP-07
    "SOL-01": [("1995-05-02", "Drain residual product into recovery drum.")],
    "SOL-02": [("1997-09-15", "Bond and earth vessel and solvent drum before transfer (clamps at solvent station).")],
    "SOL-03": [("1995-05-02", "Rinse with 40 L acetone, circulate 10 min, drain to waste solvent.")],
    "SOL-04": [("2000-07-10", "Second rinse with 20 L fresh acetone, drain.")],
    "SOL-05": [("1998-11-30", "Wipe agitator shaft and blades with xylene-soaked rag.")],
    "SOL-06": [("2008-06-23", "Before vessel entry: forced ventilation 15 min, O2/LEL test, entry permit.")],
    "SOL-07": [("1998-11-30", "Leave lid open overnight.")],
    "SOL-08": [("1995-05-02", "Wait 60 min before charging next batch (acetone vapour must clear before hot charge)."),
               ("2014-09-29", "Wait at least 15 min before charging next batch."),
               ("2015-05-18", "Wait at least 60 min before charging next batch.")],
    "SOL-09": [("1995-05-02", "Record cleaning in vessel logbook and sign.")],
    # TL-5
    "TNK-01": [("2013-09-30", "Charge polyol and dry under vacuum in VD-1 (90 °C) until water < 0.05 % (Karl Fischer).")],
    "TNK-02": [("2001-10-22", "Add 2 kg molecular sieve 3A per batch.")],
    "TNK-03": [("2005-08-29", "Nitrogen blanket on D-4 during and after isocyanate addition.")],
    "TNK-04": [("1996-04-15", "Charge 900 kg polyol PS-400 (Polioli Sereni); add 280 kg MDI prepolymer at max 2 kg/min."),
               ("2016-04-11", "Add 280 kg MDI prepolymer at max 2 kg/min.")],
    "TNK-05": [("1996-04-15", "Add 0.6 kg DBTDL.")],
    "TNK-06": [("1996-04-15", "Hold 60 °C, 45 min (Varesotti formulation sheet).")],
    "TNK-07": [("1999-11-08", "Pass through magnetic separator MS-1 before canning (see shift log 21/10/99).")],
    "TNK-08": [("2002-06-17", "Pre-dry empty cans in oven OV-1, 60 °C, 2 h.")],
    "TNK-09": [("1996-04-15", "Fill 5 L cans (Latte Brunetti) under dry nitrogen; seal."),
               ("2017-10-02", "Fill 5 L cans under dry nitrogen; seal.")],
    # QP-02
    "QC-01": [("1994-01-10", "Viscosity, Ford cup 4 / Brookfield.")],
    "QC-02": [("1994-01-10", "Fineness of grind, Hegman.")],
    "QC-03": [("1996-02-12", "Chloride on every AF-12 batch, max 400 ppm (see CR-1996-005).")],
    "QC-04": [("2003-10-20", "XRF lead screening of every incoming pigment lot (D.R. 114/2003).")],
    "QC-05": [("1994-01-10", "Retain 0.5 L sample of each batch for 1 year."),
              ("2009-11-09", "Retain 0.5 L sample of each batch for 5 years.")],
    "QC-06": [("2002-12-02", "Re-weigh each pigment addition on bench scale SC-2B, countersign.")],
    "QC-07": [("1994-01-10", "Gloss 60° on drawdown.")],
    "QC-08": [("1994-01-10", "Odour check.")],
}

# Revision documents present in the archive: (process, rev label, date, author, change note, form, supersedes)
REVISIONS = [
    ("ALK", "Rev 7", "1994-03-15", "P. Gastaldi", "Supersedes Rev 6 (1989, not in archive). Batch size 1000 kg.", "typed"),
    ("ALK", "Rev 8", "1996-01-22", "P. Gastaldi", "Added NH4Cl addition (CR-1995-009) and 12 h rest before QC (CR-1996-003).", "typed"),
    ("ALK", "Rev 9", "1998-10-05", "P. Gastaldi", "Added winter dose of bentonite (CR-1998-004).", "typed"),
    ("ALK", "Rev 10", "2001-09-12", "P. Gastaldi", "Added cooling below 40 °C before letdown (CR-2001-012).", "scan"),
    ("ALK", "Rev 12", "2007-02-19", "D. Morra", "Pigment changed from CL-77 to ZP-40 (CM-2006-004, SQ-2007-002). All other steps unchanged.", "digital"),
    ("EPX", "Rev 1", "1997-04-10", "P. Gastaldi", "New product EF-210, Part A. Batch 800 kg.", "typed"),
    ("EPX", "Rev 2", "1999-02-08", "P. Gastaldi", "Added hot box pre-heating of resin drums (CR-1999-002).", "typed"),
    ("EPX", "Rev 3", "2001-04-23", "P. Gastaldi", "Added 20 min wait before viscosity sample (as instructed by P.G.).", "scan"),
    ("EPX", "Rev 5", "2004-09-06", "P. Gastaldi", "Fillers under vacuum (CR-2004-007). Sieving per Rev 4 (CR-2003-010).", "scan"),
    ("EPX", "Rev 6", "2005-10-03", "P. Gastaldi", "Nitrogen flush of pails on FL-2 (CR-2005-006). Pails upside down 24 h.", "digital"),
    ("EPX", "Rev 7", "2012-05-14", "D. Morra", "Resin changed to KO-Epox 410 LC (SQ-2012-007). Hot box step retained.", "digital"),
    ("SOL", "Rev 1", "1995-05-02", "P. Gastaldi", "First issue of SOP-07.", "typed"),
    ("SOL", "Rev 3", "1998-11-30", "P. Gastaldi", "Added xylene wipe of agitator (CR-1998-009). Lid left open overnight.", "typed"),
    ("SOL", "Rev 4", "2000-07-10", "P. Gastaldi", "Added second acetone rinse (CR-2000-008).", "scan"),
    ("SOL", "Rev 6", "2014-09-29", "D. Morra", "Wait before next charge reduced to 15 min (CR-2014-011).", "digital"),
    ("SOL", "Rev 7", "2015-05-18", "D. Morra", "Wait before next charge restored to 60 min (CR-2015-004 cancels CR-2014-011).", "digital"),
    ("TNK", "Rev 1", "1996-04-15", "P. Gastaldi", "New product TL-5. Formulation per Isocianati Varesotti sheet.", "typed"),
    ("TNK", "Rev 2", "1999-11-08", "P. Gastaldi", "Added magnetic separator MS-1 before canning.", "typed"),
    ("TNK", "Rev 3", "2001-10-22", "P. Gastaldi", "Added molecular sieve (CR-2001-014).", "scan"),
    ("TNK", "Rev 5", "2005-08-29", "P. Gastaldi", "Nitrogen blanket during isocyanate addition (CR-2005-009). Can pre-drying per Rev 4.", "digital"),
    ("TNK", "Rev 6", "2013-09-30", "D. Morra", "Vacuum drying in VD-1 added (EQ-2013-004). Molecular sieve retained.", "digital"),
    ("QC", "Rev 1", "1994-01-10", "E. Marchisio", "QC release plan, first controlled issue.", "typed"),
    ("QC", "Rev 2", "1996-02-12", "E. Marchisio", "Added chloride test on AF-12 (CR-1996-005).", "typed"),
    ("QC", "Rev 4", "2003-10-20", "E. Marchisio", "Added XRF lead screening (CM-2003-007). Re-weighing on SC-2B per Rev 3.", "scan"),
    ("QC", "Rev 5", "2009-11-09", "E. Marchisio", "Retained samples kept 5 years (CR-2009-012).", "digital"),
]


def steps_at(proc_id: str, date: str) -> list[str]:
    """Texts of the steps of a process as they were on `date` (ISO)."""
    proc = next(p for p in PROCESSES if p["id"] == proc_id)
    out = []
    for st in proc["steps"]:
        vs = [v for v in VARIANTS[st["id"]] if v[0] <= date]
        if vs:
            out.append(vs[-1][1])
    return out
