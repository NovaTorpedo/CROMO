# CROMO architecture and decisions

## What runs where (AMD Token Factory route, the one measured for the submission)

```
                ┌──────────────────── AMD Token Factory (shared, OpenAI-compatible endpoints on AMD GPUs) ───────────────────┐
                │  REASONER  Gemma-4-31B-IT (Google DeepMind)   investigations, verdict proposals, metadata + bilingual     │
                │                                               keywords at ingest, change parsing, tripwire review, trials │
                │  VISION    Gemma-4-31B-IT (same model)        reads every scanned, faxed and handwritten archive page     │
                │  (compared on the same pages: MiniCPM-V-4.7-35B-A3B, MinerU2.5-Pro, DeepSeek-V4-Flash-Vision-Exp)         │
                └──────────────────────────────▲────────────────────────────────────────────────────────────────────────────┘
                                               │ HTTPS, team key (server-side only), ≤18 requests/min, ≤6 concurrent
┌──────────────┐   ┌───────────────────────────┴──────────────────────────────┐   ┌─────────────────────────┐
│ React UI     │──▶│ FastAPI backend (backend/cromo) — CPU, no model weights  │──▶│ Evolus (REST API)       │
│ plant map    │   │  ingest → index (BM25 + hashed n-grams + Gemma keywords) │   │  workflow (approvals)   │
│ Why-Trail    │◀──│  → investigate → verdict rules → tripwires · change-check│   │  AI Tool compare        │
│ (NDJSON)     │   │  SQLite (data/runtime) · recordings for replay           │   │  knowledge library      │
└──────────────┘   └──────────────────────────────────────────────────────────┘   └─────────────────────────┘
                                ▲
                archive/ (synthetic: page images, text layers, MES/ERP exports)
```

Every model call, reading the scans and all the reasoning, runs on AMD. The CROMO server itself does not run a
model. It handles orchestration, retrieval scoring, quote verification, the deterministic verdict rules, cost
arithmetic and the UI. The own-vLLM route (below) moves the same roles onto one AMD Instinct MI300X and adds a real
embedding model. No code changes; it is configuration only.

| Work | Where it runs | Model / method |
|---|---|---|
| Transcribing 68 scanned / faxed / handwritten pages | AMD Token Factory | Gemma-4-31B-IT (image input) |
| Document metadata + bilingual search keywords (178 documents) | AMD Token Factory | Gemma-4-31B-IT |
| Multi-hop investigation: reading passages, proposing leads, proposing a verdict (49 steps) | AMD Token Factory | Gemma-4-31B-IT |
| Change-proposal parsing, tripwire review, trial plans, ask-the-archive answers | AMD Token Factory | Gemma-4-31B-IT |
| Retrieval scoring (BM25 + hashed n-gram cosine) | CROMO server, CPU | no model |
| Quote verification, evidence-strength score, safety guards, verdict rules, costs | CROMO server, CPU | deterministic rules |
| Trial approval, recipe-revision compare, plant knowledge library | Evolus | Evolus platform |

## Pipeline
1. **Ingestion** (`ingest.py`). Born-digital pages are read from their text layer. Scans, faxes and handwritten logbooks
   go to the **VISION** model. Metadata (type, date, reference numbers, cited documents, entities, an English summary
   and bilingual keywords) comes from the reasoner, or from cached Evolus extractor records. Then the chunks are
   indexed.
2. **Index** (`index.py`). Hybrid retrieval: BM25 plus cosine over vectors, with date and type filters. The vectors
   come from the EMBEDDINGS model when one is served, otherwise from local hashed n-grams (see below).
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

## Retrieval without an embedding model
The Token Factory serves chat, vision and OCR models, but **no embedding model** (`/v1/embeddings` returns 404).
The options we weighed (zero-dollar budget):

| Option | Verdict |
|---|---|
| A local embedding model on the CROMO server's CPU (e.g. a small multilingual sentence model) | Rejected. It would make a model part of the product's AI workload that does *not* run on AMD, add ~1 GB of dependencies to the container, and slow every query on a laptop. |
| Ask the reasoner to expand every search query (extra model call per hop) | Rejected. It costs one more call per hop on a 20-requests/minute account and adds latency to every investigation. |
| Use a chat model's hidden states as embeddings | Not offered by the API. |
| **Document expansion at ingest + lexical hybrid retrieval** | **Chosen.** |

**What we do.** At ingest, the reasoner (Gemma on AMD) already makes one metadata call per document. That call now
also returns 8–16 search keywords for the document in **both English and Italian** (e.g. *gelling / impolmonimento*).
They are added to the document's search terms together with its English one-line summary, and they ride on the call
that was happening anyway, so they cost no extra request. Searches then use BM25 plus cosine over hashed word
uni/bigrams computed locally (a lexical method, not a model). This closes the main gap embeddings would have filled
here, which is cross-lingual retrieval between English questions and Italian logbooks and notices.

- The keywords change only **which** chunks a search finds. They are never shown to the model as passage text and can
  never be cited, so quote verification is unaffected.
- Expansion is applied only to model-written metadata (`meta_source` reasoner or Evolus), never to the offline fixture
  heuristic, so the rule-based baseline stays a pure lexical baseline.
- `eval/retrieval_eval.py` measures the effect against the planted key documents of each step (recall@5/@10, MRR, with
  and without expansion). The System page shows the result.
- On the own-vLLM route, `BAAI/bge-m3` (MIT, multilingual) serves real embeddings on the same MI300X and the hybrid
  index uses them instead of the hashed n-grams. The keywords stay.

## Choosing the vision / OCR model (measured, not assumed)
`scripts/compare_models.py ocr` sent the archive's 68 scanned pages (58 typed, 5 handwritten Italian logbooks, 4
faxes, 1 typed page with a handwritten note) to four Token Factory models and scored each page against the generator's
reference transcription:

| Model | Strict CER | Word F1 | Handwritten logbooks | Faxes | Typed | p50 / page | Failures |
|---|---|---|---|---|---|---|---|
| **Gemma-4-31B-IT** (used) | 2.2% | **97.9%** | **0.7%** | 7.7% | 1.9% | 16 s | 0 |
| MiniCPM-V-4.7-35B-A3B | **2.1%** | 97.3% | 0.8% | **5.1%** | 1.9% | 19 s | 0 (2 HTTP 500 retried once) |
| MinerU2.5-Pro (`/v1/ocr`) | 30.2% | 97.6% | 7.5% | 20.9% | 32.9% | 18 s | 0 |
| DeepSeek-V4-Flash-Vision-Exp | 15.0% | 94.2% | 17.3% | 14.3% | 14.6% | 11 s | 0 |

- **Strict CER** counts reading order. **Word F1** ignores it. MinerU, a document parser that returns Markdown, reads
  the words well (97.6% word F1) but lays out page blocks in a different order (e.g. the letterhead last), which strict
  CER penalises. DeepSeek's errors are real misreadings and reordered lines.
- **Decision: Gemma stays the vision model; no split.** MiniCPM's lead on strict CER is 0.1 points, within noise on 68
  pages. Gemma reads the handwritten logbooks slightly better and has the best word accuracy. MiniCPM is better on the
  4 faxes. One model for reading and reasoning also keeps the pipeline simple. The samples per page type are small;
  the numbers are reported as measured.

## AMD Token Factory specifics handled in code
- **One key, shared limits.** The account allows 20 requests/minute and 8 concurrent requests per key, for every model
  together. `llm.py` paces all roles through one sliding-window limiter (18/min) and one concurrency cap (6) per key.
- **429 / 5xx.** Retried with the server's `Retry-After`, otherwise exponential backoff with jitter. A 429 pushes the
  whole window back. Errors in both gateway shapes (`{"error"}` and `{"detail":{"error"}}`) are logged server-side only.
- **Thinking.** Gemma on the Token Factory does not think unless asked, so CROMO sends no `reasoning_effort`. An empty
  answer cut off by `max_tokens` is detected and retried.
- **Timeouts.** Non-streaming requests may take minutes when the shared service is busy, so the Token Factory route
  defaults to a 600 s read timeout (the platform allows 10 minutes).
- **Spend.** `cromo.tokenfactory.usage()` reads `GET /v1/usage` (daily allowance, requests, tokens). The benchmark
  records the meter before and after a run, and `check_amd.py` prints the remaining allowance before big runs.
- **Resumable runs.** The benchmark saves progress after every 10 documents and after every step (`--resume`), and the
  OCR comparison caches every page result, so a rate limit or a dropped connection never repeats paid work.

## The own-vLLM route (AMD Developer Cloud, ready, not used for the submission)
`deploy/amd/serve_vllm.sh` serves `google/gemma-4-26B-A4B-it` (reasoner + vision, one server) and `BAAI/bge-m3`
(embeddings) on one MI300X with ROCm and vLLM, API-key protected behind a firewall. `deploy/amd/session.sh` runs the
check, the benchmark and the recording on the droplet. This is the route the Evolus partner track requires: its agent
must use a model behind *our own* vLLM endpoint on AMD Developer Cloud. See `LINK_AMD.md`.

## Decisions and reasons
| Decision | Why |
|---|---|
| Python + FastAPI, SQLite, numpy | Small, reliable, one container; no external DB to operate. Parameterised queries only. |
| React + Vite + TypeScript, no UI kit | A distinctive, fast UI with no heavy dependencies; fonts self-hosted (Inter and IBM Plex Mono, SIL OFL). |
| One OpenAI-compatible client for every role | Switching between the AMD Token Factory and own vLLM is configuration only (`LINK_AMD.md`). |
| Gemma 4 (Google DeepMind) for reasoner **and** vision | One open multimodal model that reads the pages and reasons over them, with native function calling. On the Token Factory: Gemma-4-31B-IT; on own vLLM: Gemma-4-26B-A4B-it (mixture-of-experts, fast on one MI300X). Measured against three other AMD-hosted vision models above. |
| Lexical hybrid retrieval + model-written bilingual keywords | The Token Factory has no embedding model; see "Retrieval without an embedding model". |
| Rules decide safety-critical outcomes | LLMs find and read evidence; deterministic rules decide what may be removed. Auditable, and the dangerous error (calling a fence a fossil) is guarded twice. |
| JSON outputs validated with pydantic + retry | Robust with open models; `json_object` structured output (the Token Factory also accepts `json_schema` for Gemma). |
| Offline fixture provider | The whole product runs and is tested without a GPU; clearly labelled; it doubles as a heuristic baseline in the evaluation. |
| Recorded AMD runs + snapshot | The demo survives network or endpoint failure; replays are labelled as replays. |
| Synthetic archive with planted ground truth | No real 30-year archive is available; planted truth makes accuracy measurable; the product never reads it (tests). |
| Glass UI only on floating chrome | Translucency and blur on the top bar, spotlight, drawer and popovers; content surfaces are near-opaque so contrast never depends on the background. `prefers-reduced-transparency`, `prefers-contrast` and `prefers-reduced-motion` are honoured. |

## Security model
See `SECURITY.md`:
- Secrets are server-side only, with pre-commit and CI secret scanning. The Token Factory key never reaches the browser.
- Untrusted-document prompting with verified quotes.
- Path-traversal-safe file access, input validation, rate limits, an access token for spending endpoints, strict CSP,
  and a non-root container.
- Only synthetic data is sent to the Token Factory, whose terms keep prompts for about 2 days.
