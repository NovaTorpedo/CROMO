# LINK_AMD — connect CROMO to AMD

CROMO talks to AMD through one OpenAI-compatible client, so both routes are configuration only. Commands on your PC
run from the repo folder with the project virtualenv (`.venv\Scripts\python` on Windows).

| | Route A — AMD Token Factory (**in use**) | Route B — own vLLM on AMD Developer Cloud (ready) |
|---|---|---|
| What | Shared event endpoints on AMD GPUs, free, one team key | Your own GPU droplet: 1× AMD Instinct MI300X, ROCm + vLLM |
| Models | `Gemma-4-31B-IT` for reasoning **and** reading scans | `google/gemma-4-26B-A4B-it` (reasoner + vision) + `BAAI/bge-m3` (embeddings) |
| Retrieval | BM25 + local n-grams + Gemma's bilingual keywords (no embedding model on the Token Factory) | same, with real bge-m3 embeddings |
| Limits | 20 requests/min, 8 concurrent, daily allowance per key | none but the GPU; ≈ $1.99/h while the droplet exists |
| Evolus partner track | **Not compliant on its own** (the track asks for *your own* vLLM endpoint on AMD Developer Cloud) | Compliant |

## Route A — AMD Token Factory (what the submission measured)

1. Get the team key: [notebooks.amd.com/tokenfactory](https://notebooks.amd.com/tokenfactory) → sign in with the AMD AI
   Developer Program account → **Redeem API Key** (every team member must redeem) → **Copy to clipboard**.
2. In `.env` (never committed):
   ```
   CROMO_PROVIDER=amd
   CROMO_AMD_ROUTE=tokenfactory
   AMD_TOKEN_FACTORY=rc-...the key...
   AMD_TOKEN_FACTORY_BASE_URL=https://developer.amd.com.cn/radeon/api/v1
   CROMO_REASONER_MODEL=Gemma-4-31B-IT
   CROMO_VISION_MODEL=Gemma-4-31B-IT
   CROMO_EMBEDDINGS_MODEL=
   ```
   Every role uses the Token Factory endpoint and the team key by default. CROMO paces itself below the per-key limits
   (18 requests/min, 6 concurrent, 600 s timeout); override with `CROMO_RPM_LIMIT`, `CROMO_MAX_CONCURRENCY`,
   `CROMO_REQUEST_TIMEOUT_S`. The catalogue changes over time: `check_amd.py` lists what is served.
3. Check (prints the remaining daily allowance too):
   ```
   .venv\Scripts\python scripts\check_amd.py
   ```
   It must end with `ALL REQUIRED CHECKS PASSED`. The embeddings WARN is expected on this route.
4. Compare the vision/OCR models on the archive's 68 scanned pages (about 270 page reads; cached and resumable):
   ```
   .venv\Scripts\python scripts\compare_models.py ocr --estimate
   .venv\Scripts\python scripts\compare_models.py ocr
   .venv\Scripts\python scripts\compare_models.py ocr --retry-failed
   ```
5. Full run: ingest the whole archive on AMD, investigate all 49 steps (recorded for replay), evaluate:
   ```
   .venv\Scripts\python scripts\benchmark_amd.py --concurrency 6
   ```
   It prints an estimate first (about 700 model calls). Progress is saved after every 10 documents and every step: if the
   endpoint is overloaded or a rate limit stops it, run the same command with `--resume`. Documents and steps that hit
   endpoint errors are retried after a pause, and any that still fail are reported, never silently counted.
6. Retrieval check, README, slides, cover, public demo:
   ```
   .venv\Scripts\python eval\retrieval_eval.py
   .venv\Scripts\python scripts\update_readme.py
   .venv\Scripts\python scripts\build_submission.py
   ```
7. Run the app live: `.venv\Scripts\python -m uvicorn cromo.api:app --app-dir backend --port 8000` → http://localhost:8000.
   The header says **Live on AMD Token Factory · Gemma-4-31B-IT**. A live investigation takes a few minutes on the
   shared endpoint; for a demo, the **Replay** toggle replays the recorded AMD runs (labelled as replays).

**Usage.** The Token Factory meter is free during the event. To see it: Token Factory page → **Model Usage**, or
`check_amd.py`. The benchmark records the meter before and after the run (`tokenfactory_usage` in
`data/recorded/benchmark_amd.json`).

## Route B — own vLLM on AMD Developer Cloud (when credits arrive)

> **Credits:** a GPU droplet bills **every hour it exists, even when powered off**. Create it → run the session
> (≈ 45 min) → connect Evolus and record → **destroy it**. One MI300X is $1.99/h list price.

1. **Create the droplet.** AMD Developer Cloud → **GPU Droplets → Create GPU Droplet**: 1× **MI300X**, image **vLLM**
   (Quick Start), add your SSH key, **Create**. Wait until it is **Active** and copy its public IP.
2. **Run the one-command session on the droplet** (firewall, Gemma 4 on :8000, bge-m3 on :8002, checks, benchmark,
   recordings). Use tmux so a dropped SSH connection doesn't stop it:
   ```bash
   ssh root@<IP>
   tmux new -s cromo
   git clone https://github.com/NovaTorpedo/CROMO.git && cd CROMO
   export VLLM_API_KEY=$(openssl rand -hex 24); echo "$VLLM_API_KEY"    # write this value down: Evolus needs it
   ./deploy/amd/session.sh                 # QUICK=1 skips the Qwen A/B download; RESUME=1 continues a stopped run
   ```
   With little time left: `QUICK=1 STEPS="ALK-04 SOL-02 SOL-08" ./deploy/amd/session.sh` (marked PARTIAL, no score).
3. **Connect Evolus to the droplet's model first** (this is what the Evolus track checks), while the benchmark runs:
   Evolus → **Your models → Add model**: URL `http://<IP>:8000/v1`, model `google/gemma-4-26B-A4B-it`, key = the
   `VLLM_API_KEY` → **Test connection → Save**, note the `own/...` key. Then on your PC:
   ```
   set EVOLUS_MODEL_KEY=own/<alias shown by Evolus>
   .venv\Scripts\python scripts\evolus_setup.py extractor
   .venv\Scripts\python scripts\evolus_setup.py agent
   .venv\Scripts\python scripts\evolus_precompute.py extract --limit 20
   ```
   Paste the printed ids into `.env`, and send the agent one question from the **Ask why** page.
4. **Copy the results** (the session prints the command): `scp -r root@<IP>:/root/CROMO/data/recorded ./data/`.
   Route B results go to the same files; to keep the Token Factory results as well, copy them aside first
   (`data\recorded` → `data\recorded-tokenfactory`).
5. `update_readme.py`, `build_submission.py`, commit, push. **Destroy the droplet** (powering off does not stop billing).

## Troubleshooting
- **`HTTP 500 … CUDA out of memory` from the Token Factory.** The shared server is overloaded (it happened during our
  run). CROMO retries with backoff for about two minutes per call; if a run still stops, wait and use `--resume`.
- **`HTTP 429`.** Another teammate or process is using the shared key. CROMO honours `Retry-After`; lower
  `CROMO_RPM_LIMIT` if it persists.
- **`400 Requested model … not supported`.** The catalogue changed. `check_amd.py` lists the current model ids.
- **Empty answers with `finish_reason: length`.** Thinking used the token budget. Gemma does not think unless asked;
  leave `CROMO_REASONING_EFFORT` empty.
- **Route B: tool calling WARN.** The reasoner must run with `--enable-auto-tool-choice --tool-call-parser gemma4`.
  `serve_vllm.sh` already does this.
- **Route B: out of GPU memory.** `GEMMA_UTIL=0.55 MAXLEN=16384 RESUME=1 ./deploy/amd/session.sh`.
