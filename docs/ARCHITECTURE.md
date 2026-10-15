# CROMO architecture and decisions

```
                     ┌──────────────────────── AMD Instinct MI300X (ROCm + vLLM) ────────────────────────┐
                     │  REASONER  Gemma 4 26B-A4B-it (Google)  :8000  (tool calling, gemma4 parser)       │
                     │  VISION    same Gemma 4 server          :8000  (reads scans, faxes, handwriting)   │
                     │  EMBED     BAAI/bge-m3                  :8002  (multilingual retrieval)            │
                     └───────────────▲───────────────────────────────────────────▲────────────────────────┘
                                     │ OpenAI-compatible HTTP (API key)          │ (Evolus agent uses the same reasoner)
┌──────────────┐   ┌─────────────────┴──────────────────────────────┐   ┌──────────┴──────────────┐
│ React UI     │──▶│ FastAPI backend (backend/cromo)                │──▶│ Evolus                  │
│ periodic map │   │  ingest → index → investigate → verdict        │   │  workflow (approvals)   │
│ why-trail    │◀──│  tripwires · change-check · costs · trials     │   │  AI Tool compare        │
│ (NDJSON)     │   │  SQLite (data/runtime) · recordings for replay │   │  extractor · library    │
└──────────────┘   └────────────────────────────────────────────────┘   │  agent chat             │
                                     ▲                                   └─────────────────────────┘
                     archive/ (synthetic: page images, text layers, MES/ERP exports)
```

## Pipeline
1. **Ingestion** (`ingest.py`). Born-digital pages are read from their text layer. Scans, faxes and handwritten logbooks
   go to the **VISION** model. Metadata (type, date, reference numbers, cited documents, entities) comes from the
   reasoner or from cached Evolus extractor records. Then chunking, and embeddings from **EMBEDDINGS**.
2. **Index** (`index.py`). Hybrid retrieval: BM25 (lexical) + cosine over embeddings, with date and type filters.
3. **Investigation** (`investigate.py`). A bounded, visible multi-hop dig:
   - recipe history across archived revisions;
   - origin search;
   - follow the references found (CR-1995-009 …);
   - dependency-status checks (does the condition still exist?);
   - counter-evidence.

   The reasoner reads passages and proposes leads; a deterministic scheduler bounds the dig (9 hops). Every hop is
   streamed to the UI.
4. **Verdict** (`evidence.py`). The reasoner proposes FOSSIL / FENCE / ACTIVE / UNKNOWN with a cited chain. Then rules:
   - only quotes verified verbatim in the source can be cited;
   - claims without valid citations are dropped;
   - FOSSIL needs evidence that the condition ended and no unresolved safety counter-evidence, otherwise it goes to a
     human (UNKNOWN).

   Evidence strength is a transparent points score shown in the UI.
5. **Tripwires / Before you change** (`tripwires.py`, `changecheck.py`). The model maps words to steps; the decision is a
   deterministic, auditable rule set (fences are blocked; fossils need a trial).
6. **Trials** (`trials.py`). Evolus workflow approval loop.

## Decisions and reasons
| Decision | Why |
|---|---|
| Python + FastAPI, SQLite, numpy | Small, reliable, one container; no external DB to operate. Parameterised queries only. |
| React + Vite + TypeScript, no UI kit | A distinctive, fast UI (93 KB gzipped JS) with no heavy dependencies; fonts self-hosted (OFL). |
| One OpenAI-compatible client for every role | Switching between AMD Token Factory and own vLLM is configuration only (`LINK_AMD.md`). |
| Gemma 4 26B-A4B-it (Google DeepMind, Apache-2.0) for reasoner **and** vision | One open multimodal model: mixture-of-experts with ~4B active parameters (fast on one MI300X), native image input with OCR and handwriting recognition, native function calling (vLLM `gemma4` tool and reasoning parsers), 256K context, day-0 vLLM ROCm support. One server instead of two halves memory traffic and keeps the reading and reasoning consistent. ~52 GB bf16 weights in 0.70 of 192 GB. |
| Measured A/B instead of assumed quality | `PROFILE=compare` serves Qwen2.5-VL-7B next to Gemma; `scripts/compare_models.py` scores both on the scanned pages (CER by page type). The reasoner can be compared on the ground-truth eval (`PROFILE=qwen`, `--tag qwen`). Results are shown on the System page whichever model wins. |
| BAAI/bge-m3 (MIT) | Multilingual (IT/EN) embeddings, natively supported by vLLM's pooling runner; ungated. |
| Everything on one MI300X | ~0.78 of HBM (0.85 with the A/B model); one GPU-hour price covers the whole pipeline. |
| Rules decide safety-critical outcomes | LLMs find and read evidence; deterministic rules decide what may be removed. Auditable, and the dangerous error (calling a fence a fossil) is guarded twice. |
| JSON outputs validated with pydantic + retry | Robust with open models; `json_schema` structured output when the endpoint supports it. |
| Offline fixture provider | The whole product runs and is tested without a GPU; clearly labelled; it doubles as a heuristic baseline in the evaluation. |
| Recorded AMD runs + snapshot | The demo survives network or GPU failure; replays are labelled as replays. |
| Synthetic archive with planted ground truth | No real 30-year archive is available; planted truth makes accuracy measurable; the product never reads it (tests). |

## Security model
See `SECURITY.md`:
- Secrets are server-side only, with pre-commit and CI secret scanning.
- Untrusted-document prompting with verified quotes.
- Path-traversal-safe file access, input validation, rate limits, an access token for spending endpoints, strict CSP,
  and a non-root container.
