# LINK_AMD — switch CROMO from offline fixture mode to AMD

Everything AMD-dependent is already built and tested against a mock vLLM server. These are the only remaining
steps. Commands on your PC run from the repo folder with the project virtualenv (`.venv\Scripts\python` on Windows).

> **Credits:** an AMD Developer Cloud GPU droplet bills **every hour it exists, even when powered off**.
> Create it → run the session (≈ 45 min) → connect Evolus and record the video → **destroy it**.
> One MI300X is $1.99/h list price, so one full session costs about $3–5 of credits.

## Route B — own vLLM on AMD Developer Cloud (needed for the Evolus track; gives the measured MI300X numbers)

1. **Create the droplet.** In AMD Developer Cloud, click **GPU Droplets → Create GPU Droplet**:
   - GPU: **1× MI300X**
   - Image: **vLLM** (Quick Start)
   - Add your SSH key, then **Create**.
   - Wait until it's **Active** and copy its public IP.
2. **Run the one-command session on the droplet.** It handles the firewall, starts the three models, checks every
   endpoint, runs the full benchmark and evaluation on the GPU, and records all investigations for replay:
   ```bash
   ssh root@<IP>
   git clone https://github.com/NovaTorpedo/CROMO.git && cd CROMO
   export VLLM_API_KEY=$(openssl rand -hex 24); echo "$VLLM_API_KEY"    # write this value down: Evolus needs it
   ./deploy/amd/session.sh
   ```
   At the end it prints an `scp` command.
   (The clone needs the GitHub repository to be public. If it's still private, clone with a personal access token:
   `git clone https://<token>@github.com/NovaTorpedo/CROMO.git`.)
3. **Copy the results to your PC.** In a terminal in the CROMO folder, run the printed command:
   ```
   scp -r root@<IP>:/root/CROMO/data/recorded ./data/
   ```
4. **Connect Evolus to the AMD model and create the agent.** Steps 4–6 of `docs/EVOLUS_SETUP.md`:
   - Your models → Add model:
     - URL: `http://<IP>:8000/v1`
     - Model: `Qwen/Qwen3-30B-A3B-Instruct-2507`
     - Key: the `VLLM_API_KEY`
   - Then:
   ```
   set EVOLUS_MODEL_KEY=own/<alias shown by Evolus>
   .venv\Scripts\python scripts\evolus_setup.py library
   .venv\Scripts\python scripts\evolus_setup.py extractor
   .venv\Scripts\python scripts\evolus_setup.py agent
   .venv\Scripts\python scripts\evolus_precompute.py library --limit 178
   .venv\Scripts\python scripts\evolus_precompute.py extract --limit 20
   ```
   Paste the printed ids into `.env`.
5. **Record the demo video** while the droplet is up, following `submission/VIDEO_SCRIPT.md`. Run CROMO on your PC
   against the droplet. In `.env`, set (same key for all three):
   ```
   CROMO_PROVIDER=amd
   CROMO_REASONER_BASE_URL=http://<IP>:8000/v1
   CROMO_VISION_BASE_URL=http://<IP>:8001/v1
   CROMO_EMBEDDINGS_BASE_URL=http://<IP>:8002/v1
   CROMO_REASONER_API_KEY=<VLLM_API_KEY>
   CROMO_VISION_API_KEY=<VLLM_API_KEY>
   CROMO_EMBEDDINGS_API_KEY=<VLLM_API_KEY>
   ```
   Then start CROMO: `.venv\Scripts\python -m uvicorn cromo.api:app --app-dir backend --port 8000`, and open
   http://localhost:8000. The header says **Live on AMD**. Delete `data\runtime\cromo.db` first so CROMO starts from
   the AMD snapshot.
6. **Update the README, slides and cover with the measured numbers, and publish them:**
   ```
   .venv\Scripts\python scripts\update_readme.py
   .venv\Scripts\python scripts\build_submission.py
   git add data/recorded data/evolus_cache README.md submission && git commit -m "Measured AMD results" && git push
   ```
   The GitHub Pages demo rebuilds automatically with the AMD results.
7. **Destroy the droplet.** In AMD Developer Cloud: your droplet → **Destroy**. Powering it off does *not* stop billing.

## Route A — AMD Token Factory (event API, no billing) for live use without a droplet
1. In Token Factory (notebooks.amd.com/tokenfactory), copy the **base URL**, your **API key** and an instruct **model
   name** from the catalogue (plus a vision or embedding model if it offers one).
2. In `.env` set:
   ```
   CROMO_PROVIDER=amd
   CROMO_AMD_ROUTE=tokenfactory
   CROMO_REASONER_BASE_URL=<base URL ending in /v1>
   CROMO_REASONER_API_KEY=<token factory key>
   CROMO_REASONER_MODEL=<model>
   ```
   If the catalogue has a vision or embedding model, also set the `CROMO_VISION_*` / `CROMO_EMBEDDINGS_*` lines. Without
   them, scans use recorded transcriptions and retrieval uses local embeddings; the System page says so.
3. `.venv\Scripts\python scripts\check_amd.py` must end with `ALL REQUIRED CHECKS PASSED`; every failure prints what to fix.
4. `.venv\Scripts\python scripts\benchmark_amd.py`, then step 6 above.

## Troubleshooting
- **`check_amd.py` says tool calling WARN.** The reasoner must run with `--enable-auto-tool-choice --tool-call-parser hermes`. `serve_vllm.sh` already does this.
- **A model is still downloading.** `./deploy/amd/serve_vllm.sh logs` on the droplet shows progress.
- **Out of GPU memory.** Lower `REASONER_UTIL` (e.g. `REASONER_UTIL=0.5 ./deploy/amd/serve_vllm.sh start`) or set `REASONER_MAXLEN=16384`.
