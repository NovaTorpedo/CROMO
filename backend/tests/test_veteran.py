"""Veteran interview mode: questions, testimony as an informal source, re-investigation, purge before evaluation."""

import asyncio

from fastapi.testclient import TestClient

from cromo import db, investigate, llm, security, veteran


def test_testimony_flow(built):
    from cromo.api import app

    security._hits.clear()
    with TestClient(app) as c:
        r0 = c.post("/api/steps/EPX-05/veteran-questions")
        assert r0.status_code == 200, r0.text
        q = r0.json()
        assert len(q["questions"]) >= 3
        assert c.post("/api/steps/EPX-05/testimony", data={"name": "F. Bellone", "answer": "short"}).status_code == 422
        bad = c.post("/api/steps/EPX-05/testimony", data={"name": "F. Bellone", "answer": "x" * 40},
                     files={"audio": ("a.exe", b"MZ", "application/octet-stream")})
        assert bad.status_code == 415
        r = c.post("/api/steps/EPX-05/testimony", data={
            "name": "F. Bellone", "role": "shift foreman 1985-2016",
            "answer": "Gastaldi added the 20 minute wait in 2001 because the old viscometer gave wrong readings on warm samples. "
                      "The diluent addition warms the batch, so we waited for it to cool before sampling."})
        assert r.status_code == 200, r.text
        acc = r.json()["acc"]
        assert acc.startswith("INT-")
        doc = c.get(f"/api/docs/{acc}").json()
        assert doc["doc_type"] == "interview record" and doc["pages_data"][0]["source"] == "testimony"

    async def go():
        v = await investigate.investigate("EPX-05", store=False)
        await llm.aclose()
        return v

    v = asyncio.run(go())
    used = {e["acc"] for e in v["evidence"].values()}
    if acc in used and v["verdict"] != "UNKNOWN":
        assert v["strength"]["grade"] != "Strong"  # testimony alone is never strong evidence
    assert veteran.purge() >= 1
    assert db.q1("SELECT COUNT(*) n FROM documents WHERE acc LIKE 'INT-%'")["n"] == 0
