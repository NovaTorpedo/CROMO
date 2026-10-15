# LINK_AMD — switch CROMO from offline fixture mode to AMD

Everything AMD-dependent is already built and tested against a mock vLLM server. These are the only remaining
steps. Commands run from the repo folder with the project virtualenv
(`.venv\Scripts\python` on Windows, `.venv/bin/python` elsewhere).

> **Credits:** an AMD Developer Cloud GPU droplet bills **every hour it exists, even when powered off**.
> Create it → run steps 2–8 in one sitting (≈ 1.5 h) → **destroy it** (step 10).
> One MI300X is $1.99/h list price, so one full session costs about $3–4 of credits.

---

## Route A — AMD Token Factory (event API, no billing)
Use this for the public demo's live mode. It also works if you can't create a Developer Cloud droplet.

1. In Token Factory (notebooks.amd.com/tokenfactory), copy the **base URL**, your **API key** and the **model names** from the catalogue.
2. In `.env` set:
   ```
   CROMO_PROVIDER=amd
   CROMO_AMD_ROUTE=tokenfactory
   CROMO_REASONER_BASE_URL=<token factory base URL, ending in /v1>
   CROMO_REASONER_API_KEY=<token factory key>
   CROMO_REASONER_MODEL=<an instruct model from the catalogue, e.g. a Qwen3 or Llama model>
   ```
   If the catalogue has a **vision** model (e.g. Qwen2.5-VL) or an **embedding** model, also set the
   `CROMO_VISION_*` / `CROMO_EMBEDDINGS_*` lines (same URL and key). If it has none, leave them empty: scans then
   use the recorded transcriptions and retrieval uses local embeddings. The System page labels this clearly.
3. Continue with **step 3** below.

## Route B — own vLLM on AMD Developer Cloud (required for the Evolus track)

1. **Create the droplet.** In AMD Developer Cloud, click **GPU Droplets → Create**:
   - GPU: **1× MI300X**
   - Image: **vLLM** (Quick Start)
   - Add your SSH key, then **Create**.
   - When it's **Active**, copy its public IP.
2. **Start the models** (this downloads ~80 GB of open-model weights the first time, about 10 min):
   ```bash
   ssh root@<IP>
   git clone https://github.com/NovaTorpedo/CROMO.git && cd CROMO/deploy/amd
   export VLLM_API_KEY=$(openssl rand -hex 24); echo "$VLLM_API_KEY"   # copy this value; it is your endpoint password
   ./firewall.sh
   ./serve_vllm.sh start          # reasoner :8000, vision :8001, embeddings :8002 - waits until healthy
   rocm-smi --showmeminfo vram > /root/rocm-smi.txt
   ```
   In your local `.env` set (same key for all three):
   ```
   CROMO_PROVIDER=amd
   CROMO_AMD_ROUTE=vllm
   CROMO_REASONER_BASE_URL=http://<IP>:8000/v1
   CROMO_VISION_BASE_URL=http://<IP>:8001/v1
   CROMO_EMBEDDINGS_BASE_URL=http://<IP>:8002/v1
   CROMO_REASONER_API_KEY=<VLLM_API_KEY>
   CROMO_VISION_API_KEY=<VLLM_API_KEY>
   CROMO_EMBEDDINGS_API_KEY=<VLLM_API_KEY>
   ```
   (The model names in `.env.example` already match what `serve_vllm.sh` serves.)

## Then, for either route

3. **Check the endpoints.** `scripts/check_amd.py` must end with `ALL REQUIRED CHECKS PASSED`; every failure prints what to fix.
   ```
   .venv\Scripts\python scripts\check_amd.py
   ```
   If it reports `structured output (json_schema) OK`, set `CROMO_STRUCTURED_OUTPUT=json_schema` in `.env`.
4. **Re-ingest, investigate, evaluate and benchmark on AMD, and record every run for demo replay** (one command, ~20–40 min):
   ```
   .venv\Scripts\python scripts\benchmark_amd.py --rocm-smi rocm-smi.txt
   ```
   (Copy `rocm-smi.txt` from the droplet first with `scp root@<IP>:/root/rocm-smi.txt .` — optional.)
   This writes:
   - `data/recorded/benchmark_amd.json` and `data/recorded/eval_amd.json`
   - `data/recorded/runs/*.json` (the replays)
   - `data/recorded/snapshot.db` (the AMD-computed results the public demo starts from)
5. **Look at the results.** Run `.venv\Scripts\python -m uvicorn cromo.api:app --app-dir backend --port 8000` and open
   http://localhost:8000. The header must say **Live on AMD**, and the System page shows the measured numbers.
6. **Record the demo video** following `submission/VIDEO_SCRIPT.md` while the endpoints are up.
7. **Connect the model in Evolus** (Route B endpoint; Evolus requires your own vLLM on AMD):
   1. In Evolus, go to **Your models → Add model**.
   2. Fill in:
      - Base URL: `http://<IP>:8000/v1`
      - Model: `Qwen/Qwen3-30B-A3B-Instruct-2507`
      - API key: `<VLLM_API_KEY>`
   3. Click **Test connection**, then **Save**, and note the model key it shows (`own/<alias>`).
   4. Then run:
   ```
   set EVOLUS_MODEL_KEY=own/<alias>
   .venv\Scripts\python scripts\evolus_setup.py extractor
   .venv\Scripts\python scripts\evolus_setup.py library
   .venv\Scripts\python scripts\evolus_setup.py agent
   .venv\Scripts\python scripts\evolus_precompute.py library --limit 178
   .venv\Scripts\python scripts\evolus_precompute.py extract --limit 20
   ```
   Paste the ids each script prints into `.env`. Then ask the plant agent one question from the **Ask why** page (tick
   "Also ask the Evolus plant agent"), so the workspace usage shows the AMD model in use.
8. **Commit the recorded results** (they contain no secrets; the pre-commit scan checks):
   ```
   git add data/recorded data/evolus_cache && git commit -m "Recorded AMD benchmark, evaluation and demo replays"
   ```
9. **Flip the public demo.** On the hosting service, set `CROMO_PROVIDER=amd` with the Token Factory variables (live mode),
   or leave it in fixture mode. Either way the AMD-computed snapshot and the replays are shown, labelled with model,
   hardware and date. See `docs/HOSTING.md`.
10. **Destroy the droplet.** In AMD Developer Cloud: your droplet → **Destroy**. Powering it off does *not* stop billing.
    Evolus will then fail to reach the model. That's fine after judging; re-create it if you need the agent live again.
