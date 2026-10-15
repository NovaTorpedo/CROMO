"""Planted ground truth for the synthetic archive.

Written to eval/ground_truth.json by build_archive.py. The CROMO pipeline must
never read this file or this module (enforced by tests/test_isolation.py).

Per step:
  label          FOSSIL | FENCE | ACTIVE | UNKNOWN
  why            one-line explanation of the planted story
  key            documents that carry the reason / its end (doc keys)
  also           other documents that legitimately support claims about the step
  deps           dependencies the reason rests on and whether they still hold
  tags           difficulty features exercised by the step
"""

F, N, A, U = "FOSSIL", "FENCE", "ACTIVE", "UNKNOWN"


def T(label, why, key=(), also=(), deps=(), tags=()):
    return {"label": label, "why": why, "key": list(key), "also": list(also),
            "deps": [dict(name=d[0], type=d[1], holds=d[2]) for d in deps], "tags": list(tags)}


TDS_ALK = ["TDS-AF12", "QP02-BASIS-2021"]
TDS_EPX = ["TDS-EF210"]
TDS_TNK = ["TDS-TL5"]

STEPS = {
    # ---------------- AF-12 --------------------------------------------------
    "ALK-01": T(A, "Binder of the enamel.", key=TDS_ALK),
    "ALK-02": T(A, "Anti-corrosive pigment.", key=TDS_ALK, also=["SQ-2007-002", "CM-2006-004"]),
    "ALK-03": T(U, "Lecithin inherited from a lost 1984 sheet; nobody knows why.", key=["MM-1997-03-10", "EMAIL-2016-09-21"],
                tags=["no-reason"]),
    "ALK-04": T(F, "Levi case: NH4Cl neutralised excess alkali of 1995 chromate pigment lots; supplier fixed it in 1996 and the "
                   "pigment was replaced by neutral zinc phosphate in 2007.",
                key=["DR-1995-031", "LT-1995-118", "CR-1995-009", "FAX-1996-03-04", "CM-2006-004", "SQ-2007-002", "LT-2020-044"],
                also=["LOG-1995-12-02", "EMAIL-2019-04-08", "CR-1996-005"],
                deps=[("alkaline chromate pigment CL-77 (Cromopigmenti Lazzeretti)", "material", False)],
                tags=["levi", "multi-hop", "counter-claim", "handwritten-support", "italian"]),
    "ALK-05": T(F, "Winter bentonite dose needed while finished goods sat in unheated warehouse M2; heated M5 since 2011.",
                key=["DR-1998-007", "CR-1998-004", "EQ-2011-006", "EMAIL-2023-01-12"],
                deps=[("finished goods stored in unheated warehouse M2", "facility", False)], tags=["multi-hop"]),
    "ALK-06": T(A, "Dispersion to fineness spec.", key=TDS_ALK),
    "ALK-07": T(N, "Flash fire 2001: white spirit (flash point ~39 C) added to hot batch. White spirit is still the letdown solvent.",
                key=["IR-2001-007", "CR-2001-012", "EMAIL-2017-10-03"], also=["SDS-2022-WS", "CM-2004-011"],
                deps=[("white spirit letdown solvent (flash point ~39 C)", "material", True)],
                tags=["safety", "dependency-still-present"]),
    "ALK-08": T(A, "Letdown to viscosity.", key=TDS_ALK, also=["SDS-2022-WS"]),
    "ALK-09": T(A, "Driers and anti-skin.", key=TDS_ALK),
    "ALK-10": T(F, "12 h rest to detect livering from alkaline chromate pigment; no livering since 1996, pigment gone 2007, "
                   "0 h vs 12 h viscosity identical in 2020 study.",
                key=["CR-1996-003", "MM-2008-05-13", "LT-2020-044", "CM-2006-004"], also=["DR-1995-031", "SQ-2007-002"],
                deps=[("alkaline chromate pigment CL-77 (Cromopigmenti Lazzeretti)", "material", False)],
                tags=["reason-split", "multi-hop"]),
    "ALK-11": T(A, "50 µm filtration required by OEM customers.", key=TDS_ALK),
    # ---------------- EF-210 -------------------------------------------------
    "EPX-01": T(F, "Warm-up protected the old hydraulic drive seals; drive replaced by electric VFD in 2019.",
                key=["ML-1996-D1", "WI-1997-02", "EQ-2019-002"],
                deps=[("hydraulic drive of disperser D-1", "equipment", False)], tags=["equipment-replaced"]),
    "EPX-02": T(F, "Hot box against crystallisation of ALTAREP E-19; low-crystallisation KO-410 LC since 2012.",
                key=["DR-1999-012", "CR-1999-002", "SQ-2012-007", "LET-2012-04-02"], also=["EQ-1999-004", "EMAIL-2016-01-20"],
                deps=[("crystallising epoxy resin ALTAREP E-19 (Resine Altamira)", "material", False)],
                tags=["red-herring-supplier-still-active", "resolved-counter-evidence"]),
    "EPX-03": T(A, "Epoxy binder.", key=TDS_EPX, also=["SQ-2012-007"]),
    "EPX-04": T(A, "Reactive diluent lowers viscosity.", key=TDS_EPX),
    "EPX-05": T(U, "20 min wait added on an engineer's verbal instruction; nobody knows why.", key=["EMAIL-2009-11-05"],
                tags=["no-reason", "speculation"]),
    "EPX-06": T(N, "Original reason (lumpy bags) is gone, but since 2018 the screen catches big-bag liner fragments.",
                key=["QN-2018-009", "ML-2024-VS1"], also=["DR-2003-015", "CR-2003-010", "SQ-2010-003"],
                deps=[("foreign matter from big-bag liners", "hazard", True)], tags=["reason-drift", "looks-like-fossil"]),
    "EPX-07": T(N, "Vacuum deaeration prevents pinholes from micro-silica (EUR 42k claim 2004); micro-silica still required.",
                key=["CL-2004-003", "LT-2004-061", "CR-2004-007", "MM-2021-02-09"],
                deps=[("micro-silica filler", "material", True)], tags=["quality", "dependency-still-present"]),
    "EPX-08": T(A, "Defoamer releases air during application.", key=TDS_EPX),
    "EPX-09": T(A, "EEW controls mixing ratio.", key=TDS_EPX),
    "EPX-10": T(F, "N2 flush protected amine hardener on shared line FL-2; hardeners moved to dedicated FL-3 in 2017; "
                   "Part A is not air-sensitive.",
                key=["CR-2005-006", "EQ-2017-003", "TDS-KO410"],
                deps=[("amine hardener (Part B) filled on shared line FL-2", "equipment", False)], tags=["reason-split"]),
    "EPX-11": T(A, "Filling and labelling.", key=TDS_EPX),
    "EPX-12": T(U, "Upside-down storage; only contradictory hearsay.", key=["LOG-2006-02-14", "EMAIL-2014-06-02"],
                tags=["contradictory", "speculation", "italian"]),
    # ---------------- SOP-07 -------------------------------------------------
    "SOL-01": T(A, "Product recovery / waste reduction.", key=["SOP07-RAT-2016"]),
    "SOL-02": T(N, "Static spark near-miss 1997; legal requirement for flammable liquids; acetone still used.",
                key=["NM-1997-004", "CR-1997-006", "CM-2004-011"],
                deps=[("flammable cleaning solvent (acetone)", "material", True)],
                tags=["safety", "prompt-injection-target", "dependency-still-present"]),
    "SOL-03": T(A, "Main cleaning rinse.", key=["SOP07-RAT-2016"]),
    "SOL-04": T(F, "Second rinse for zero carry-over on BW-90 white for Carrozzerie Vetta; BW-90 discontinued 2015.",
                key=["SPEC-2000-VETTA", "CR-2000-008", "PM-2015-001"], also=["EMAIL-2023-03-06"],
                deps=[("white topcoat BW-90 for Carrozzerie Vetta", "product", False)], tags=["customer-spec", "biggest-cost"]),
    "SOL-05": T(F, "Xylene wipe for chlorinated rubber (CR-55) residues; CR-55 discontinued 2009.",
                key=["CR-1998-009", "PM-2009-002"], also=["EHS-2021-07"],
                deps=[("chlorinated rubber paints CR-55", "product", False)], tags=["reason-split", "multi-hop"]),
    "SOL-06": T(N, "Operator overcome by vapour 2008; regional confined-space rule.",
                key=["IR-2008-003", "CR-2008-005", "RN-2010-12"],
                deps=[("vessel entry into confined spaces with solvent vapour", "hazard", True)], tags=["safety", "regulatory", "italian"]),
    "SOL-07": T(U, "Lid open overnight: two contradictory guesses, no record.", key=["EMAIL-2012-09-17"],
                tags=["contradictory"]),
    "SOL-08": T(N, "Wait reduced to 15 min in 2014, caused LEL alarm and defects in 2015, reverted to 60 min.",
                key=["CR-2014-011", "DR-2015-006", "CR-2015-004"],
                deps=[("residual acetone vapour with hot charging", "hazard", True)], tags=["reverted-change", "safety"]),
    "SOL-09": T(A, "ISO 9001 traceability.", key=["SOP07-RAT-2016"]),
    # ---------------- TL-5 ---------------------------------------------------
    "TNK-01": T(A, "Water must be below 0.05 % for moisture-cure PU.", key=TDS_TNK, also=["EQ-2013-004"]),
    "TNK-02": T(F, "Sieve for wet PS-400 polyol; VD-1 drying since 2013 and dry NP-310 since 2016; effect not measurable.",
                key=["DR-2001-019", "CR-2001-014", "EQ-2013-004", "SQ-2016-005", "LT-2018-022"],
                deps=[("wet polyol PS-400 (Polioli Sereni)", "material", False)], tags=["multi-hop"]),
    "TNK-03": T(N, "Lid blown off 2005 from moisture ingress; isocyanate still moisture-sensitive.",
                key=["IR-2005-011", "CR-2005-009", "MM-2019-10-15"],
                deps=[("moisture-sensitive MDI prepolymer (isocyanate)", "material", True)], tags=["safety", "dependency-still-present"]),
    "TNK-04": T(A, "Exotherm control.", key=TDS_TNK),
    "TNK-05": T(A, "Catalyst for cure speed.", key=TDS_TNK),
    "TNK-06": T(U, "45 min hold from a lost supplier sheet; only a generic hypothesis.", key=["EMAIL-2020-06-09"],
                tags=["hypothesis-only"]),
    "TNK-07": T(N, "Iron swarf from worn D-4 impeller (handwritten 1999 logbook only); impeller still steel and wearing.",
                key=["LOG-1999-10-21", "ML-2024-D4"], also=["ML-2022-MS1"],
                deps=[("wearing steel impeller of disperser D-4", "equipment", True)],
                tags=["handwritten-only", "italian", "dependency-still-present"]),
    "TNK-08": T(F, "Cans pre-dried because Latte Brunetti cans stood outdoors; dry, wrapped Corvino cans since 2017.",
                key=["DR-2002-008", "CR-2002-005", "SQ-2017-004"],
                deps=[("damp cans from Latte Brunetti stored outdoors", "material", False)], tags=["supplier-changed"]),
    "TNK-09": T(A, "Moisture-cure product canned under N2.", key=TDS_TNK),
    # ---------------- QP-02 --------------------------------------------------
    "QC-01": T(A, "Release criterion.", key=["QP02-BASIS-2021"], also=["TDS-AF12"]),
    "QC-02": T(A, "Release criterion.", key=["QP02-BASIS-2021"], also=["TDS-AF12"]),
    "QC-03": T(A, "Chloride test exists because NH4Cl is still added (ALK-04); becomes a fossil if ALK-04 is removed.",
               key=["CR-1996-005", "LT-2020-044"], also=["QP02-BASIS-2021"],
               deps=[("ammonium chloride addition in AF-12 (ALK-04)", "step", True)], tags=["coupled-step"]),
    "QC-04": T(F, "XRF lead screening required by D.R. 114/2003 for plants using lead pigments; lead pigments gone 2006, "
                  "decree repealed 2018.",
               key=["RN-2003-114", "CM-2003-007", "CM-2006-004", "RN-2018-052"], also=["AUD-2021-03"],
               deps=[("Regional Decree 114/2003", "regulation", False), ("lead-containing pigments", "material", False)],
               tags=["regulation-repealed", "red-herring-audit", "italian"]),
    "QC-05": T(N, "Lost EUR 95k claim in 2009 for lack of retained sample; customer agreements require 5 years.",
               key=["CL-2009-007", "CR-2009-012", "QA-2015-AGR"], also=["EMAIL-2022-05-30"],
               deps=[("customer quality agreements requiring 5-year retention", "regulation", True)], tags=["looks-like-waste"]),
    "QC-06": T(F, "Re-weighing compensated drift of scale SC-2; replaced by calibrated WS-10 in 2014.",
               key=["ML-2002-SC2", "DR-2002-011", "CR-2002-007", "EQ-2014-005"],
               deps=[("drifting platform scale SC-2", "equipment", False)], tags=["equipment-replaced"]),
    "QC-07": T(A, "Gloss release criterion.", key=["QP02-BASIS-2021", "TDS-AF12"]),
    "QC-08": T(U, "Odour check with no criterion and unknown origin.", key=["MM-2016-11-08"], tags=["no-reason"]),
}

INJECTION_DOCS = ["EMAIL-2024-03-12"]

# Change events for the Tripwires screen, with the expected consequences.
TRIPWIRES = [
    {"id": "TW-SOLVENT", "event": {"type": "material_substitution", "process": "ALK",
                                   "from": "white spirit D40", "to": "high-flash isoparaffin solvent (flash point 62 °C)"},
     "expected": {"ALK-07": "fence_dependency_removed", "ALK-08": "review_required"}},
    {"id": "TW-RESIN", "event": {"type": "supplier_switch", "process": "EPX",
                                 "from": "KO-Epox 410 LC (Kessler-Ondra)", "to": "standard grade liquid epoxy resin (crystallising type)"},
     "expected": {"EPX-02": "fossil_reactivated", "EPX-03": "review_required"}},
    {"id": "TW-IMPELLER", "event": {"type": "equipment_replacement", "process": "TNK",
                                    "from": "D-4 mild steel impeller", "to": "ceramic-coated impeller (no wear)"},
     "expected": {"TNK-07": "fence_dependency_removed"}},
    {"id": "TW-ORGANOTIN", "event": {"type": "regulation_change", "process": "TNK",
                                     "from": "DBTDL organotin catalyst allowed", "to": "organotin catalysts restricted from 2027"},
     "expected": {"TNK-05": "review_required"}},
    {"id": "TW-NH4CL", "event": {"type": "step_removal", "process": "ALK", "from": "ALK-04 ammonium chloride addition", "to": "removed"},
     "expected": {"QC-03": "becomes_fossil"}},
    {"id": "TW-CLEANER", "event": {"type": "material_substitution", "process": "SOL",
                                   "from": "acetone", "to": "water-based alkaline cleaner (non-flammable)"},
     "expected": {"SOL-02": "fence_dependency_removed", "SOL-08": "fence_dependency_removed",
                  "SOL-06": "fence_still_required", "SOL-03": "review_required"}},
]

# "Before you change" proposals with the expected decision.
CHANGE_CHECKS = [
    {"proposal": "Remove step SOL-02 (bonding and earthing) to save time", "expected": "blocked"},
    {"proposal": "Remove the ammonium chloride addition from AF-12 (ALK-04)", "expected": "allowed_with_trial"},
    {"proposal": "Shorten the cooling hold before letdown in AF-12 from 30 to 5 minutes", "expected": "blocked"},
    {"proposal": "Remove EPX-05, the 20 minute wait before sampling", "expected": "caution"},
    {"proposal": "Drop the second acetone rinse in SOP-07", "expected": "allowed_with_trial"},
    {"proposal": "Stop retaining batch samples for 5 years; keep them 1 year", "expected": "blocked"},
    {"proposal": "Switch the epoxy resin to a cheaper standard grade resin", "expected": "caution"},
    {"proposal": "Remove the magnetic separator MS-1 from TL-5", "expected": "blocked"},
    {"proposal": "Reduce the wait after cleaning from 60 to 15 minutes", "expected": "blocked"},
    {"proposal": "Remove the molecular sieve from TL-5", "expected": "allowed_with_trial"},
]
