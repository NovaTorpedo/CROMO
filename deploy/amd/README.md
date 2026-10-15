# CROMO on AMD Instinct MI300X (ROCm + vLLM)

| File | What it does |
|---|---|
| `session.sh` | One command on the droplet: firewall, start the models, run `check_amd.py` + `benchmark_amd.py` in a CROMO container next to the GPU, leave the results in `data/recorded/`. |
| `serve_vllm.sh` | `start` / `status` / `logs` / `stop` the three vLLM servers. Uses the vLLM container of the AMD "vLLM Quick Start" image when it runs with host networking, otherwise the official `vllm/vllm-openai-rocm` image. |
| `firewall.sh` | ufw: SSH + vLLM ports only. `ALLOW_FROM=<ip>` restricts vision and embeddings to one IP. |
| `compose.amd.yml` | Compose override used by `session.sh` (host network, results volume). |

## Models and why
| Port | Role | Model | Why |
|---|---|---|---|
| 8000 | Reasoner | `Qwen/Qwen3-30B-A3B-Instruct-2507` (Apache-2.0) | Mixture-of-experts with ~3B active parameters: fast; strong at JSON and tool calling. Served with `--enable-auto-tool-choice --tool-call-parser hermes` (the parser vLLM documents for Qwen; Evolus agents use tools). Non-thinking variant, so no `<think>` overhead. |
| 8001 | Vision | `Qwen/Qwen2.5-VL-7B-Instruct` (Apache-2.0) | Reads scans, faxes and handwritten Italian logbooks; well supported by vLLM on ROCm. |
| 8002 | Embeddings | `BAAI/bge-m3` (MIT) | Multilingual (IT/EN) retrieval; a native pooling model in vLLM (no extra flags). |

## Sharing one GPU (192 GB HBM3)
Each server gets a fixed fraction of GPU memory (`--gpu-memory-utilization`). They start **in order**, each waiting
until the previous one is healthy, so every server profiles memory against what is actually free:

| Server | Fraction | ≈ GB | Weights (bf16) | Rest |
|---|---|---|---|---|
| Reasoner | 0.55 | 105 | ~61 GB | KV cache for 32k context and concurrent requests |
| Vision | 0.25 | 48 | ~17 GB | KV cache + image tokens (16k context) |
| Embeddings | 0.08 | 15 | ~1.2 GB | batching |

The total is 0.88, which leaves headroom for the ROCm runtime. Adjust with environment variables, e.g.
`REASONER_UTIL=0.5 REASONER_MAXLEN=16384 ./serve_vllm.sh start`, or swap models with `REASONER_MODEL=...`. If you change
models, update the `CROMO_*_MODEL` names in CROMO's `.env`.

## Security
- Every endpoint requires `--api-key` (`VLLM_API_KEY`); an unprotected vLLM endpoint would be open to anyone.
- Only SSH and the three ports are open.
- The droplet keeps no CROMO secrets except the generated `.env.amd`, which `session.sh` deletes after the run.

## Cost control
- Billing runs per hour while the droplet **exists** (powered off still bills).
- Typical session: ~10 min model download, ~30 min benchmark, then connect Evolus and record the video. Then **Destroy**.
