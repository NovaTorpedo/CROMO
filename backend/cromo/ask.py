"""'Ask about any step' - route questions about a step to its investigation; answer other plant questions
from the archive with citations (every claim must cite a retrieved passage)."""

from __future__ import annotations

import time

from . import archive, index, llm
from .schemas import AskOut, StepMatchOut


async def ask(question: str) -> dict:
    t0 = time.perf_counter()
    steps = [{"id": s["id"], "instruction": s["instruction"]} for s in archive.steps()]
    m = await llm.run_task("ask.match", {"question": question, "steps": steps}, StepMatchOut)
    if m.step_id and m.is_question_about_step and m.step_id.upper() in {s["id"] for s in steps}:
        return {"type": "step", "step_id": m.step_id.upper(), "question": question}
    passages = await index.search(question, k=6)
    res = await llm.run_task("ask.answer", {"question": question, "passages": passages}, AskOut)
    by_id = {p["id"]: p for p in passages}
    claims = []
    for c in res.claims:
        ids = [i for i in c.evidence if i in by_id]
        if ids:
            claims.append({"text": c.text, "sources": [{k: by_id[i][k] for k in ("acc", "page", "date", "doc_type", "title",
                                                                                  "text", "line_start", "line_end")}
                                                       for i in ids]})
    insufficient = res.insufficient_evidence or not claims
    return {"type": "answer", "question": question,
            "answer": res.answer if not insufficient else
            "The archive does not contain enough evidence to answer this reliably.",
            "claims": claims, "insufficient_evidence": insufficient,
            "related_steps": [s for s in res.related_steps if s in {x["id"] for x in steps}],
            "provider": llm.mode(), "model": llm.model_name("reasoner"),
            "duration_s": round(time.perf_counter() - t0, 2)}
