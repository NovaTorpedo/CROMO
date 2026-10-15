# CROMO on AMD Instinct MI300X (ROCm + vLLM)

| File | What it does |
|---|---|
| `session.sh` | One command on the droplet: firewall, start the models, run `check_amd.py` + `benchmark_amd.py` in a CROMO container next to the GPU, leave the results in `data/recorded/`. |
| `serve_vllm.sh` | `start` / `status` / `logs` / `stop` the vLLM servers of a `PROFILE` (`gemma` default, `compare`, `qwen`). Uses the vLLM container of the AMD "vLLM Quick Start" image when it runs with host networking, otherwise the official `vllm/vllm-openai-rocm` image. |
| `firewall.sh` | ufw: SSH + vLLM ports only. `ALLOW_FROM=<ip>` restricts vision and embeddings to one IP. |
| `compose.amd.yml` | Compose override used by `session.sh` (host network, results volume). |

## Models and why
| Port | Role | Model | Why |
|---|---|---|---|
| 8000 | Reasoner **and** vision | `google/gemma-4-26B-A4B-it` (Gemma 4, Google DeepMind, Apache-2.0) | Open multimodal mixture-of-experts (~4B active of 25B): reads scans, faxes and handwritten Italian logbooks (native OCR/handwriting) and does all reasoning. Served with `--enable-auto-tool-choice --tool-call-parser gemma4 --reasoning-parser gemma4` (Evolus agents use tools), `--limit-mm-per-prompt '{"image": 2}'`, `--mm-processor-kwargs '{"max_soft_tokens": 1120}'` for dense pages, and `VLLM_ATTENTION_BACKEND=TRITON_ATTN` on ROCm. |
| 8001 | Vision A/B (`compare` profile only) | `Qwen/Qwen2.5-VL-7B-Instruct` (Apache-2.0) | Second reader for `scripts/compare_models.py vision`, so Gemma's reading quality is measured, not assumed. |
| 8002 | Embeddings | `BAAI/bge-m3` (MIT) | Multilingual (IT/EN) retrieval; a native pooling model in vLLM (no extra flags). |

## Sharing one GPU (192 GB HBM3)
Each server gets a fixed fraction of GPU memory (`--gpu-memory-utilization`). They start **in order**, each waiting
until the previous one is healthy, so every server profiles memory against what is actually free:

| Profile | Server | Fraction | ≈ GB | Weights (bf16) |
|---|---|---|---|---|
| `gemma` (default) | Gemma 4 26B-A4B (reasoner + vision) | 0.70 | 134 | ~52 GB, rest KV cache + image tokens (32k context) |
| | bge-m3 | 0.08 | 15 | ~1.2 GB |
| `compare` (`session.sh` default) | Gemma 4 26B-A4B | 0.62 | 119 | ~52 GB |
| | Qwen2.5-VL-7B (A/B) | 0.15 | 29 | ~17 GB |
| | bge-m3 | 0.08 | 15 | ~1.2 GB |
| `qwen` (fallback / reasoner A/B) | Qwen3-30B-A3B :8000 · Qwen2.5-VL-7B :8001 · bge-m3 :8002 | 0.55 · 0.25 · 0.08 | | |

Totals stay at or below 0.88, which leaves headroom for the ROCm runtime. Adjust with environment variables, e.g.
`GEMMA_UTIL=0.55 MAXLEN=16384 ./serve_vllm.sh start`, or swap the model with `GEMMA_MODEL=...`. If you change
models, update the `CROMO_*_MODEL` names in CROMO's `.env`.

## Short on time or after a failure
Run `session.sh` inside `tmux new -s cromo`; reattach with `tmux attach -t cromo`.
- `QUICK=1` serves Gemma + bge-m3 only and skips the vision A/B.
- `STEPS="ALK-04 SOL-02 SOL-08"` investigates only those steps, giving a partial run with no evaluation score.
- `RESUME=1` keeps the running servers and continues the benchmark from its saved progress.
- `finalize_partial.sh` publishes what an interrupted run measured, marked PARTIAL.

Details and the prize impact of each case: [docs/FALLBACK.md](../../docs/FALLBACK.md).

## Security
- Every endpoint requires `--api-key` (`VLLM_API_KEY`); an unprotected vLLM endpoint would be open to anyone.
- Only SSH and the vLLM ports (8000–8002) are open.
- The droplet keeps no CROMO secrets except the generated `.env.amd`, which `session.sh` deletes after the run.

## Cost control
- Billing runs per hour while the droplet **exists** (powered off still bills).
- Typical session: ~10 min model download, ~30 min benchmark, then connect Evolus and record the video. Then **Destroy**.
