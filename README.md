<p align="center"><img src="docs/img/home.png" alt="CROMO plant map: every process step as a tile, coloured by verdict" width="900"></p>

# CROMO — every factory runs on reasons nobody remembers

**CROMO recovers why each step of a factory recipe exists.** It reads 30 years of a plant's own paperwork:
scans, faxes, handwritten logbooks, change requests, incident reports, emails. Then it shows:

- which steps are **fossils**: waste whose reason is gone. It shows what each costs per year.
- which steps are **fences**: they look pointless but protect safety or quality. It blocks their removal.
- the moment a change makes a step useless, or makes a safeguard dangerous to remove (**tripwires**).

It investigates rather than chats. Every claim is tied to a quote verified in a source document, the evidence strength
is graded by transparent rules, and a human approves every change through an Evolus workflow. **Google DeepMind's open
Gemma 4 reads every page and does all the reasoning on AMD GPUs**, through the AMD Token Factory.

> Built for the **AMD Developer Hackathon: ACT III**, track *Intelligent Industry*.
> **All plant data is synthetic** (a fictional paint company, see [below](#the-synthetic-archive)).

**Public demo (read-only, recorded AMD results):** https://novatorpedo.github.io/CROMO/ · **Run it yourself:** `docker compose up` ([quickstart](#quickstart))

---

## The story

In *Chromium*, a chapter of Primo Levi's *The Periodic Table* (1975), a young chemist fixes a batch of anti-rust paint
that keeps turning to jelly by adding ammonium chloride. The fault was in one pigment delivery.

Twenty years later, the bad pigment is long gone. Yet the factory still adds ammonium chloride to every batch, and nobody
can say why. The step had become a **fossil**. *Cromo* is Italian for chromium.

There is the opposite case. In *A Canticle for Leibowitz* (1959), monks faithfully preserve blueprints they no longer
understand. And G. K. Chesterton's *fence* (1929) warns: don't tear down a fence until you know why it was put up. Some
steps that look pointless are load-bearing.

Every plant is full of both. Process engineers, quality/EHS managers and plant managers inherit recipes with steps
whose reasons left with retired staff. Meanwhile AI optimisers are starting to propose "remove this, shorten that".
CROMO tells you which is which, with evidence. We recreated Levi's case in our synthetic archive: CROMO finds it.

## What it does

| | |
|---|---|
| <img src="docs/img/investigation.png" width="430"> | **The Why-Trail.** Ask why about any step (Ctrl K anywhere). CROMO digs, hop by hop, and streams each hop: recipe history, the change request that introduced the step, the references it cites, whether each condition still holds, counter-evidence. The verdict and the key evidence come first, by year; the full dig is one click away. |
| <img src="docs/img/fence.png" width="430"> | **Fossil / Fence / Active / Unknown.** Only quotes verified verbatim in the source can be cited; uncited claims are dropped. A FOSSIL needs evidence that its reason ended and no unresolved safety evidence, otherwise it goes to a person. **Evidence strength** (Strong / Moderate / Weak) is a transparent points score. |
| <img src="docs/img/tripwires.png" width="430"> | **What if… the plant changes? (tripwires)** Every recovered reason records what it depends on (supplier, material, equipment, regulation). Simulate a change, and CROMO says which steps just became fossils, which fences are affected, and which old fossils come back to life. Example: buying a cheaper, crystallising epoxy resin again reactivates the hot-box step. |
| <img src="docs/img/change-check.png" width="430"> | **What if… we change a step?** "Remove step 12", "shorten the hold from 30 to 5 minutes", "switch resin supplier": CROMO answers **blocked / caution / allowed with trial**, with the fences and evidence involved. It's also a REST endpoint (`POST /api/v1/change-check`): *the tool that tells AI optimizers which fences not to tear down.* |
| <img src="docs/img/trials.png" width="430"> | **Safe trials via Evolus.** CROMO never deletes a step. For a fossil it drafts a controlled trial (scope, measurements, acceptance criteria, rollback) and sends it through an **Evolus workflow**. The workflow writes the brief for the approving engineer and records the request and the decision. The status comes back to CROMO. |
| <img src="docs/img/system.png" width="430"> | **System: where it runs, measured.** Which model runs each role and where, the measured latency, throughput and Token Factory usage, the comparison of four AMD-hosted vision models on the archive's scans, the retrieval check and the evaluation. |

Also in the app:
- **Ask a veteran.** For UNKNOWN or weakly evidenced steps, CROMO prepares interview questions for experienced staff. It
  records the answer as dated testimony and re-investigates. Testimony is an informal source, so it can never make the
  evidence "Strong" on its own.
- **Ask the archive.** Free-text questions about the plant, answered from the archive with every claim tied to a document.
- **Replay.** Investigations replay recorded AMD runs, labelled as replays, so a live pitch survives an endpoint outage.

## Results

Measured against the planted ground truth: 49 steps, of which 12 fossils, 9 fences, 22 active and 6 unknown.
The product never reads this file (enforced by tests).

**Missing a fence is the dangerous error**, so we report FENCE recall and the false-FOSSIL rate first.

<!-- RESULTS:START -->
| | Rule-based baseline (offline fixture provider, no LLM) | CROMO on the AMD Token Factory · Gemma-4-31B-IT |
|---|---|---|
| FENCE recall | 56% | 89% |
| False-FOSSIL rate | 11% | 0% |
| Fences called fossils | 1 (SOL-08) | 0 |
| Accuracy, 4 classes | 65% | 80% |
| Citation precision | 61% | 71% |
| Tripwire effects found | 36% of 11 | 73% of 11 |
| Change-check decisions correct | 70% of 10 | 70% of 10 |
| Prompt-injection test | passed | passed |
| Ingestion throughput / VLM transcription CER | n/a (recorded transcriptions) | 1.5 pages/min · CER 2.2% |
| Median investigation time / cost per full plant audit | n/a | 21 min · $0.04 on the Token Factory meter (1351 requests, 1.3M tokens; free during the event) |

*Measured on the shared AMD Token Factory during the event, 6 requests at a time: a metadata call took 47 s at the median (p95 185 s), with outages and rejected requests in between (545 of 1351 requests during the run were rejected by the endpoint and retried). The throughput reflects the shared endpoint's load, not GPU capacity.*

*36 of 68 scanned pages were not re-sent: the endpoint was rejecting image requests (overloaded), so the ingest reused Gemma-4-31B-IT's own readings of those pages, made on the same AMD endpoint with the same prompt during the OCR comparison. The ingest time does not include those readings.*

**Reading the scans: 4 AMD-hosted models on the same 68 scanned pages** (character error rate vs. the reference, lower is better; word F1 ignores reading order):

| Model | Strict CER | Word F1 | fax (n=4) | handwritten logbook (n=5) | typed + handwritten note (n=1) | typed / scanned (n=58) | p50 / page | Failures |
|---|---|---|---|---|---|---|---|---|
| `Gemma-4-31B-IT` (CROMO) | 2.2% | 97.9% | 7.7% | 0.7% | 1.6% | 1.9% | 16 s | 0/68 |
| `MinerU2.5-Pro` | 30.2% | 97.6% | 20.9% | 7.5% | 24.3% | 32.9% | 18 s | 0/68 |
| `DeepSeek-V4-Flash-Vision-Exp` | 15.0% | 94.2% | 14.3% | 17.3% | 27.8% | 14.6% | 11 s | 0/68 |
| `MiniCPM-V-4.7-35B-A3B` | 2.1% | 97.3% | 5.1% | 0.8% | 5.3% | 1.9% | 19 s | 0/68 |

**Retrieval without an embedding model** (49 steps, searching with the step text): Gemma's bilingual keywords rank the first key document higher (mean reciprocal rank 0.29 → 0.39); the share of key documents in the top 5 / top 10 stays 40% → 40% / 66% → 66%.
<!-- RESULTS:END -->

The baseline column comes from CROMO's deterministic fixture provider, a keyword heuristic that never sees the
answers. The AMD columns and tables are filled in by `scripts/benchmark_amd.py`, `scripts/compare_models.py ocr`,
`eval/retrieval_eval.py` and `scripts/update_readme.py` from measured runs. We never type benchmark numbers by hand.

## How it works

```
archive (scans, faxes, logbooks, PDFs, emails) ─► ingestion ─► hybrid index ─► investigation ─► verdict + guards ─► map / what-if / trials
              VISION + REASONER: Gemma 4 (Google DeepMind) on the AMD Token Factory      rules, quotes, costs: CROMO server
```

1. **Ingestion.** Born-digital pages are read from their text layer. Scans, faxes and handwritten Italian logbooks go to
   Gemma. Gemma also writes each document's metadata and **bilingual (English + Italian) search keywords**.
2. **Investigation.** A bounded, visible multi-hop dig: recipe history, origin, follow references, dependency status,
   counter-evidence. Gemma reads passages and proposes leads; a deterministic scheduler bounds the dig.
3. **Verdict and guards.** The model proposes; rules decide what may be removed. Quotes are verified against the source,
   uncited claims are dropped, and the safety guards can only downgrade a verdict to UNKNOWN.
4. **Actions.** Tripwire alerts, the change-check API, and trial plans approved through Evolus.

Details, including what runs where: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

### AMD stack
| Role | Model (license) | Where |
|---|---|---|
| Reasoner | **Gemma-4-31B-IT** (Gemma 4, Google DeepMind, open weights) | AMD Token Factory (OpenAI-compatible, AMD GPUs) |
| Vision | **the same Gemma 4 model**: OCR of typed, faxed and handwritten Italian pages | AMD Token Factory |
| Retrieval | BM25 + local n-gram vectors + **Gemma's bilingual keywords** (no embedding model is served on the Token Factory) | CROMO server (CPU) |

**Gemma 4 is CROMO's brain and eyes.** One open model reads every scanned page, reads the passages, proposes leads and
verdicts, parses change proposals and writes the search keywords.

**Chosen by measurement.** `scripts/compare_models.py ocr` sent the archive's 68 scanned pages to four AMD-hosted
models (Gemma-4-31B-IT, MiniCPM-V-4.7-35B-A3B, MinerU2.5-Pro, DeepSeek-V4-Flash-Vision-Exp) and scored them against
the reference text. Gemma and MiniCPM-V are within 0.1 points of each other; Gemma reads the handwritten logbooks best
and keeps one model for reading and reasoning. The table is in [Results](#results) and on the System page.

**Built for a shared endpoint.** The Token Factory allows 20 requests/minute and 8 concurrent requests per team key.
CROMO paces every role through one limiter, honours `Retry-After`, retries overloaded-server errors with backoff, reads
the usage meter before big runs, and makes every long run resumable ([LINK_AMD.md](LINK_AMD.md)).

**Own GPU, same code.** With AMD Developer Cloud credits, [`deploy/amd/session.sh`](deploy/amd/session.sh) serves
`google/gemma-4-26B-A4B-it` and `BAAI/bge-m3` with vLLM on one AMD Instinct MI300X (ROCm), API-key protected, and
re-runs the whole benchmark there. Switching is configuration only.

### Evolus building blocks (driven through the REST API)
| Block | Use in CROMO |
|---|---|
| **Workflow** "CROMO · Trial approval" | Fossil → trial plan → AI Tool brief for the engineer → approval record → decision recorded → status back in CROMO (live, created via `POST /workflows`) |
| **AI Tool `compare`** | "What changed when this step was added?" between recipe revisions (17 cached results) |
| **Knowledge library** | The 178-document plant archive for an Evolus plant agent |
| **Document extractor + agent** | Ready (`scripts/evolus_setup.py`); they run on our own vLLM model once a Developer Cloud droplet is up |

Setup and status: [docs/EVOLUS_SETUP.md](docs/EVOLUS_SETUP.md).

## Quickstart
```bash
git clone https://github.com/NovaTorpedo/CROMO.git && cd CROMO
docker compose up --build        # http://localhost:8000
```
With no configuration it runs in **offline fixture mode**: no GPU, no keys, clearly labelled in the UI. With the
recorded snapshot it shows the AMD results. To connect AMD and Evolus, copy `.env.example` to `.env` and follow
[LINK_AMD.md](LINK_AMD.md) (Token Factory: one key and two model names).

Without Docker (Python 3.12, Node 22):
```bash
python -m venv .venv && .venv/bin/pip install -r backend/requirements-dev.txt   # Windows: .venv\Scripts\...
cd frontend && npm ci && npm run build && npm test && cd ..
.venv/bin/python -m uvicorn cromo.api:app --app-dir backend --port 8000
.venv/bin/python -m pytest backend/tests                 # incl. mock-endpoint tests of the live path and security tests
.venv/bin/python eval/run_eval.py --rerun                # evaluation against the planted ground truth
```

Before your first commit, enable the secret-scanning pre-commit hook (gitleaks is pinned and checksum-verified):
```bash
git config core.hooksPath .githooks
.venv/bin/python scripts/install_gitleaks.py
```

## Configuration
All settings are environment variables. See [`.env.example`](.env.example) (names and comments only):
- `CROMO_PROVIDER`, `CROMO_AMD_ROUTE` (`tokenfactory` or `vllm`)
- `AMD_TOKEN_FACTORY` (team key) and `AMD_TOKEN_FACTORY_BASE_URL`
- `CROMO_{REASONER,VISION,EMBEDDINGS}_{BASE_URL,API_KEY,MODEL}` (on the Token Factory route only the model names)
- `CROMO_RPM_LIMIT`, `CROMO_MAX_CONCURRENCY`, `CROMO_REQUEST_TIMEOUT_S` (route defaults when empty)
- `EVOLUS_*`
- `CROMO_ACCESS_TOKEN`: required for writes and model/Evolus calls from anywhere except this machine or a private
  network. **Set it on any internet-facing deployment.**
- `CROMO_ALLOWED_ORIGINS`, `CROMO_API_DOCS` (development only)

## The synthetic archive
There is no public 30-year plant archive, so we built one. **Valdorso Coatings S.p.A.** is a **fictional** paint plant;
its people, suppliers, customers, regulations and agency are invented. The archive has 178 documents from 1994–2026:
- current and superseded recipes;
- deviation, incident and near-miss reports;
- change requests and supplier qualifications;
- invoices and maintenance logs;
- lab reports;
- regional notices (Italian);
- meeting minutes and emails;
- handwritten Italian shift logbooks and faxes, rendered with realistic noise.

The ground truth plants deliberate difficulties:
- red herrings and contradictory documents;
- reasons split across several documents;
- a reason recoverable only from a handwritten page;
- a change that was later reverted;
- fences whose dependency is still present;
- a document with an injected instruction aimed at AI systems.

It is reproducible (`python generator/build_archive.py`, seeded). The truth lives in `eval/ground_truth.json`, which the
product never reads.

## Design
The interface takes inspiration from layered-glass design languages without copying any: translucent glass only on
floating chrome (top bar, "Ask why" spotlight, document drawer, popovers), near-opaque content surfaces so text contrast
never depends on what is behind it, one blue accent for interaction, and four verdict colours reserved for verdicts
(the Unknown tiles are also dashed, so the map reads without colour). Light and dark themes; `prefers-reduced-motion`,
`prefers-reduced-transparency` and `prefers-contrast` are honoured. Fonts: Inter and IBM Plex Mono (SIL OFL); icons:
Lucide (ISC).

## Security
- Keys live server-side only; `.env` is git-ignored. A pre-commit hook and CI run gitleaks and a scanner that blocks any value from the local `.env`.
- Archive text is untrusted data: delimited in prompts, quotes verified, instruction-like text flagged and excluded (tested).
- Strict input validation, path-traversal-safe file access, CSP and security headers, rate limits, and an access token for endpoints that spend model calls or credits.
- Non-root container with a health check; pinned dependencies (`pip-audit` / `npm audit` in CI).
- Only synthetic data is sent to the Token Factory.

See [SECURITY.md](SECURITY.md).

## Limitations (honest)
- The archive is synthetic. Results on it do not guarantee results on a real plant's messier archive.
- The verdict depends on what the archive contains. CROMO can only say UNKNOWN when a reason was never written down; it routes those to people.
- The Token Factory is a shared, rate-limited service: a live investigation takes minutes, and its latency depends on
  the load from other teams. The measured throughput reflects the account's request limit, not the GPU.
- Retrieval is lexical (plus Gemma's bilingual keywords) because the Token Factory serves no embedding model.
- The offline fixture provider is a heuristic baseline used to run the product without a GPU. It is not the AI system,
  and the UI labels it everywhere.
- Costs use synthetic plant parameters; the formula and every input are shown, so a plant can substitute its own.
- The public demo is static: it replays recorded runs. Live investigations need the full app with AMD endpoints.

## Licenses
- Code: MIT ([LICENSE](LICENSE)).
- Models: Gemma 4 (Google DeepMind, Gemma terms of use / open weights); the compared models under their own licences.
- UI fonts: Inter and IBM Plex Mono (SIL OFL 1.1). Archive rendering fonts: IBM Plex, Fraunces, Courier Prime,
  Libre Baskerville, Caveat, Reenie Beanie (SIL OFL 1.1); Special Elite and Homemade Apple (Apache-2.0); license files in
  `generator/fonts/`.
- Icons: Lucide (ISC). Frontend: React (MIT), Vite (MIT).
- Backend: FastAPI, Starlette, Pydantic, httpx, uvicorn, numpy, Pillow (MIT/BSD/HPND).
