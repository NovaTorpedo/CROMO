# LINK_AMD — switch CROMO from offline fixture mode to AMD

Everything AMD-dependent is already built and tested against a mock vLLM server. These are the only remaining
steps. Commands on your PC run from the repo folder with the project virtualenv (`.venv\Scripts\python` on Windows).

> **Credits:** an AMD Developer Cloud GPU droplet bills **every hour it exists, even when powered off**.
> Create it → run the session (≈ 45 min) → connect Evolus and record the video → **destroy it**.
> One MI300X is $1.99/h list price, so one full session costs about $3–5 of credits.

> **Short on time, only a Token Factory key, or a run that failed partway?** See [docs/FALLBACK.md](docs/FALLBACK.md)
> for the minimum steps in each case and which prizes each one keeps. Run `session.sh` inside `tmux new -s cromo` so a
> dropped SSH connection doesn't stop it; `RESUME=1 ./deploy/amd/session.sh` continues an interrupted run.

## Route B — own vLLM on AMD Developer Cloud (needed for the Evolus track; gives the measured MI300X numbers)

1. **Create the droplet.** In AMD Developer Cloud, click **GPU Droplets → Create GPU Droplet**:
   - GPU: **1× MI300X**
   - Image: **vLLM** (Quick Start)
   - Add your SSH key, then **Create**.
   - Wait until it's **Active** and copy its public IP.
2. **Run the one-command session on the droplet.** It handles the firewall, starts Gemma 4 (reasoner + vision, :8000),
   bge-m3 (:8002) and, for the A/B test, Qwen2.5-VL (:8001); checks every endpoint, compares the two vision models on the
   scanned pages, runs the full benchmark and evaluation on the GPU with Gemma, and records all investigations for replay:
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
     - Model: `google/gemma-4-26B-A4B-it`
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
   CROMO_VISION_BASE_URL=http://<IP>:8000/v1
   CROMO_EMBEDDINGS_BASE_URL=http://<IP>:8002/v1
   CROMO_REASONER_API_KEY=<VLLM_API_KEY>
   CROMO_VISION_API_KEY=<VLLM_API_KEY>
   CROMO_EMBEDDINGS_API_KEY=<VLLM_API_KEY>
   ```
   Then start CROMO: `.venv\Scripts\python -m uvicorn cromo.api:app --app-dir backend --port 8000`, and open
   http://localhost:8000. The header says **Live on AMD**. Delete `data\runtime\cromo.db` first so CROMO starts from
   the AMD snapshot. (The model names default to Gemma 4 in `.env.example`: `CROMO_REASONER_MODEL` and
   `CROMO_VISION_MODEL` = `google/gemma-4-26B-A4B-it`.)
5b. **Optional: reasoner A/B (Gemma 4 vs Qwen3-30B-A3B), about 40 more minutes of droplet time.** After the video,
   on the droplet:
   ```bash
   PROFILE=qwen ./deploy/amd/session.sh
   ```
   It swaps the servers to the all-Qwen stack and benchmarks it into `eval_amd_qwen.json` / `benchmark_amd_qwen.json` (the
   Gemma results are not touched). Repeat step 3 to copy the results; the System page then shows both reasoners side by
   side on the 49-step eval. Finish with step 6 and 7.
6. **Update the README, slides and cover with the measured numbers, and publish them:**
   ```
   .venv\Scripts\python scripts\update_readme.py
   .venv\Scripts\python scripts\build_submission.py
   git add data/recorded data/evolus_cache README.md submission && git commit -m "Measured AMD results" && git push
   ```
   The GitHub Pages demo rebuilds automatically with the AMD results.
7. **Destroy the droplet.** In AMD Developer Cloud: your droplet → **Destroy**. Powering it off does *not* stop billing.

## Route A — AMD Token Factory (event API, no billing) for live use without a droplet
1. In Token Factory (notebooks.amd.com/tokenfactory), copy the **base URL**, your **API key** and a **model name** from
   the catalogue. Prefer a **Gemma 4** model if the catalogue lists one (it covers reasoner *and* vision); otherwise any
   instruct model, plus a vision or embedding model if offered.
2. In `.env` set:
   ```
   CROMO_PROVIDER=amd
   CROMO_AMD_ROUTE=tokenfactory
   CROMO_REASONER_BASE_URL=<base URL ending in /v1>
   CROMO_REASONER_API_KEY=<token factory key>
   CROMO_REASONER_MODEL=<model>
   CROMO_HARDWARE_LABEL=AMD Token Factory (AMD Instinct GPUs)
   ```
   `.env.example` presets the vision model to Gemma 4. Set `CROMO_VISION_MODEL` to the catalogue's image-capable model
   id (the same as the reasoner if it's Gemma 4), or leave it **empty** if there is none. Do the same for
   `CROMO_EMBEDDINGS_MODEL`. Without them, scans use recorded transcriptions and retrieval uses local embeddings; the
   System page, slides and submission text say so, and no transcription accuracy is claimed.
3. `.venv\Scripts\python scripts\check_amd.py` must end with `ALL REQUIRED CHECKS PASSED`; every failure prints what to fix.
4. `.venv\Scripts\python scripts\benchmark_amd.py --concurrency 4` (if a rate limit stops it, rerun with `--resume`),
   then step 6 above. On this route no GPU-hour audit cost is claimed: the Token Factory has no per-GPU billing.
5. Evolus: the Evolus track asks for *your own vLLM endpoint on AMD Developer Cloud*, so this route alone may not
   qualify for it. Ask the organisers before relying on it (docs/FALLBACK.md, case 1).

## Troubleshooting
- **`check_amd.py` says tool calling WARN.** The reasoner must run with `--enable-auto-tool-choice --tool-call-parser gemma4` (Gemma 4) or `hermes` (Qwen). `serve_vllm.sh` already does this.
- **A model is still downloading.** `./deploy/amd/serve_vllm.sh logs` on the droplet shows progress.
- **Out of GPU memory.** Lower `GEMMA_UTIL` (e.g. `GEMMA_UTIL=0.55 ./deploy/amd/serve_vllm.sh start`) or set `MAXLEN=16384`.
- **Gemma fails to start on ROCm.** Check `serve_vllm.sh logs`; the script already sets `VLLM_ATTENTION_BACKEND=TRITON_ATTN`. As a fallback, `PROFILE=qwen` serves the previous all-Qwen stack (then set the `CROMO_*_MODEL` names to the Qwen models).
