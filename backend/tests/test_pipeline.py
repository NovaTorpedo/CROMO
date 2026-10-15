"""Pipeline behaviour in offline fixture mode: verdicts, citations, evidence validation, costs."""

import pytest

from cromo import archive, costs, db, evidence, investigate
from cromo.schemas import ChainClaim, ConcludeOut, Counter, Dependency
from cromo.text import quote_in


def test_archive_ingested(built):
    assert db.q1("SELECT COUNT(*) n FROM documents")["n"] == len(archive.list_accessions())
    assert db.q1("SELECT COUNT(*) n FROM chunks WHERE vector IS NULL")["n"] == 0


def test_every_step_has_a_verdict(built):
    vs = investigate.all_stored()
    assert set(vs) == {s["id"] for s in archive.steps()}
    assert all(v["verdict"] in ("FOSSIL", "FENCE", "ACTIVE", "UNKNOWN") for v in vs.values())


def test_every_citation_is_a_verified_quote_from_its_document(built):
    for sid, v in investigate.all_stored().items():
        for eid in v["strength"]["cited"]:
            e = v["evidence"][eid]
            assert e["verified"] and not e["suspicious"], (sid, eid)
            text = db.q1("SELECT text FROM documents WHERE acc=?", (e["acc"],))["text"]
            assert quote_in(e["quote"], text), f"{sid} {eid}: quote not in {e['acc']}"


def test_claims_cite_evidence(built):
    for v in investigate.all_stored().values():
        for c in v["chain"]:
            assert c["evidence"], "uncited claim survived validation"


def test_levi_case_offline(built):
    v = investigate.stored("ALK-04")
    assert v["verdict"] == "FOSSIL"
    assert v["origin_year"] in (1995, 1996)


def _ev(i, acc="ACC-0001", stance="reason", verified=True, suspicious=False, quote="flash fire at the open manhole"):
    return {"id": i, "acc": acc, "date": "2001-06-19", "doc_type": "incident report", "stance": stance, "quote": quote,
            "claim": "x", "verified": verified, "suspicious": suspicious, "entities": [], "page": 1}


def test_uncited_claims_are_removed_and_verdict_downgraded():
    ev = {"E1": _ev("E1", verified=False)}
    out = ConcludeOut(verdict="FOSSIL", chain=[ChainClaim(claim="made up", evidence=["E9"]),
                                                ChainClaim(claim="unverified", evidence=["E1"])])
    v, notes, removed = evidence.validate(out, ev)
    assert removed == 2 and v["chain"] == [] and v["verdict"] == "UNKNOWN"


def test_fossil_requires_ended_dependency():
    ev = {"E1": _ev("E1"), "E2": _ev("E2", stance="status")}
    out = ConcludeOut(verdict="FOSSIL", chain=[ChainClaim(claim="c", evidence=["E1"])],
                      dependencies=[Dependency(name="white spirit", holds=True, evidence=["E2"])])
    v, notes, _ = evidence.validate(out, ev)
    assert v["verdict"] == "UNKNOWN"


def test_fossil_with_unresolved_safety_counter_evidence_goes_to_human():
    ev = {"E1": _ev("E1"), "E2": _ev("E2", stance="status"), "E3": _ev("E3", stance="counter", quote="operator burns after flash fire")}
    out = ConcludeOut(verdict="FOSSIL", chain=[ChainClaim(claim="c", evidence=["E1"])],
                      dependencies=[Dependency(name="old pigment", holds=False, evidence=["E2"])],
                      counter_evidence=[Counter(claim="fire risk", evidence=["E3"], resolved=False)])
    v, notes, _ = evidence.validate(out, ev)
    assert v["verdict"] == "UNKNOWN" and any("counter-evidence" in n for n in notes)


def test_strength_grades_are_transparent():
    ev = {f"E{i}": _ev(f"E{i}", acc=f"ACC-000{i}") for i in range(1, 5)}
    v = {"verdict": "FENCE", "chain": [{"claim": "c", "evidence": ["E1", "E2"]}],
         "dependencies": [{"name": "d", "holds": True, "evidence": ["E3"]}], "counter_evidence": [], "origin_evidence": []}
    st = evidence.strength(v, ev)
    assert st["grade"] in ("Strong", "Moderate") and sum(b["points"] for b in st["breakdown"]) == st["score"]
    v["verdict"] = "UNKNOWN"
    assert evidence.strength(v, ev)["grade"] == "Insufficient"


def test_cost_formula_matches_inputs():
    st = archive.step("ALK-04")
    c = costs.step_cost(st)
    pp = archive.plant_parameters()
    per_run = 1.6 * archive.materials()["RM-118"]["price_eur"] + 10 / 60 * pp["labor_rate_eur_per_h"]
    assert c["per_run_eur"] == pytest.approx(per_run, abs=0.01)
    assert c["annual_eur"] == round(per_run * pp["volumes"]["ALK"]["per_year"])
