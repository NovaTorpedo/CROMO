#!/usr/bin/env bash
# One-shot AMD session on the MI300X droplet (AMD Developer Cloud, "vLLM" Quick Start image, Docker installed).
#
#   git clone https://github.com/NovaTorpedo/CROMO.git && cd CROMO
#   export VLLM_API_KEY=$(openssl rand -hex 24); echo "$VLLM_API_KEY"   # keep it: Evolus needs it
#   tmux new -s cromo          # so a dropped SSH connection does not kill the run (reattach: tmux attach -t cromo)
#   ./deploy/amd/session.sh
#
# Variants (environment variables):
#   QUICK=1    short on time: Gemma + bge-m3 only, no vision A/B (saves the Qwen download and ~10 min)
#   STEPS="ALK-04 SOL-02 ..."  investigate only these steps (a partial run: no evaluation score, marked partial)
#   RESUME=1   after a failure: keeps running servers, skips finished parts, continues the benchmark where it stopped
#   PROFILE=qwen  optional afterwards: reasoner A/B (Gemma 4 vs Qwen3) on the same eval, written to *_qwen files
#   STRUCTURED_OUTPUT=json_object  if check_amd.py says json_schema is not supported
#
# What it does (about 30-45 min, most of it the benchmark):
#   1. firewall (SSH + vLLM ports, API-key protected)
#   2. starts the models with vLLM on the GPU and waits until healthy
#   3. builds the CROMO evaluation container and runs it next to the GPU (host network, no internet hop):
#      scripts/check_amd.py -> compare_models.py -> benchmark_amd.py (ingest, investigate, eval, latency, cost, replays)
#   4. leaves the results in data/recorded/ - copy them to your PC with the scp command printed at the end
# Progress is saved after every step, so a failure never loses what was already measured (see RESUME=1 and
# docs/FALLBACK.md). The vLLM servers keep running so you can connect them to Evolus.
# DESTROY the droplet when done (it bills while it exists).
set -euo pipefail
cd "$(dirname "$0")/../.."
: "${VLLM_API_KEY:?Set VLLM_API_KEY first: export VLLM_API_KEY=\$(openssl rand -hex 24)}"
say() { printf '\033[1;33m[cromo]\033[0m %s\n' "$*"; }
trap 'rm -f .env.amd' EXIT   # the key file never outlives the session, even when a step fails

say "1/4 firewall"
./deploy/amd/firewall.sh >/dev/null

# Gemma 4 serves REASONER + VISION. The 'compare' profile also starts Qwen2.5-VL so the vision A/B test can run.
if [ "${QUICK:-0}" = 1 ]; then export PROFILE="${PROFILE:-gemma}"; else export PROFILE="${PROFILE:-compare}"; fi
[ "$PROFILE" = compare ] && export GEMMA_UTIL="${GEMMA_UTIL:-0.62}"
if [ "${RESUME:-0}" = 1 ] && curl -sf -H "Authorization: Bearer $VLLM_API_KEY" http://127.0.0.1:8000/v1/models >/dev/null \
   && curl -sf -H "Authorization: Bearer $VLLM_API_KEY" http://127.0.0.1:8002/v1/models >/dev/null; then
  say "2/4 resume: the model servers are already up, keeping them"
else
  say "2/4 starting the models, profile $PROFILE (first start downloads the weights)"
  ./deploy/amd/serve_vllm.sh start
fi
mkdir -p data/recorded
(rocm-smi --showproductname --showmeminfo vram --showuse > data/recorded/rocm-smi.txt 2>&1) || true

say "3/4 building the CROMO evaluation container"
umask 077
BENCH_ARGS=""
# PROFILE=qwen: optional reasoner A/B. Benchmarks the all-Qwen stack into *_qwen files; the Gemma results stay untouched.
if [ "$PROFILE" = qwen ]; then
  REASONER_MODEL="${QWEN_REASONER:-Qwen/Qwen3-30B-A3B-Instruct-2507}"; VISION_MODEL="${QWEN_VISION:-Qwen/Qwen2.5-VL-7B-Instruct}"
  VISION_PORT=8001; BENCH_ARGS="--tag qwen"
fi
[ -n "${STEPS:-}" ] && BENCH_ARGS="$BENCH_ARGS --steps $STEPS"
[ "${RESUME:-0}" = 1 ] && BENCH_ARGS="$BENCH_ARGS --resume"
{
  echo "CROMO_PROVIDER=amd"
  echo "CROMO_AMD_ROUTE=vllm"
  echo "CROMO_REASONER_BASE_URL=http://127.0.0.1:8000/v1"
  echo "CROMO_REASONER_API_KEY=${VLLM_API_KEY}"
  echo "CROMO_REASONER_MODEL=${REASONER_MODEL:-google/gemma-4-26B-A4B-it}"
  echo "CROMO_VISION_BASE_URL=http://127.0.0.1:${VISION_PORT:-8000}/v1"
  echo "CROMO_VISION_API_KEY=${VLLM_API_KEY}"
  echo "CROMO_VISION_MODEL=${VISION_MODEL:-google/gemma-4-26B-A4B-it}"
  if [ "$PROFILE" = compare ]; then
    echo "CROMO_VISION_ALT_BASE_URL=http://127.0.0.1:8001/v1"
    echo "CROMO_VISION_ALT_API_KEY=${VLLM_API_KEY}"
    echo "CROMO_VISION_ALT_MODEL=${QWEN_VISION:-Qwen/Qwen2.5-VL-7B-Instruct}"
  fi
  echo "CROMO_EMBEDDINGS_BASE_URL=http://127.0.0.1:8002/v1"
  echo "CROMO_EMBEDDINGS_API_KEY=${VLLM_API_KEY}"
  echo "CROMO_EMBEDDINGS_MODEL=${EMBED_MODEL:-BAAI/bge-m3}"
  echo "CROMO_STRUCTURED_OUTPUT=${STRUCTURED_OUTPUT:-json_schema}"
  echo "CROMO_MAX_CONCURRENCY=12"
  echo "CROMO_EVOLUS_ENABLED=false"
  echo "CROMO_HARDWARE_LABEL=AMD Instinct MI300X (192 GB HBM3), ROCm + vLLM, AMD Developer Cloud"
} > .env.amd
COMPOSE="docker compose -f docker-compose.yml -f deploy/amd/compose.amd.yml --profile eval"
$COMPOSE build eval

say "4/4 check + benchmark (records every investigation for demo replay)"
$COMPOSE run --rm eval python scripts/check_amd.py || {
  say "check failed: look at the FAIL lines above. If structured output is the only problem, rerun with STRUCTURED_OUTPUT=json_object RESUME=1."
  exit 1; }
if [ "$PROFILE" = compare ]; then
  if [ "${RESUME:-0}" = 1 ] && [ -f data/recorded/vision_comparison.json ]; then
    say "vision A/B already measured, skipping"
  else
    say "vision A/B: Gemma 4 vs Qwen2.5-VL on every scanned page (CER + latency)"
    $COMPOSE run --rm eval python scripts/compare_models.py vision || say "vision comparison failed (non-blocking)"
  fi
fi
# shellcheck disable=SC2086
if ! $COMPOSE run --rm eval python scripts/benchmark_amd.py --rocm-smi data/recorded/rocm-smi.txt --concurrency 8 $BENCH_ARGS; then
  say "benchmark stopped. Its progress is saved. Options (docs/FALLBACK.md, case 3):"
  say "  continue:          RESUME=1 ./deploy/amd/session.sh"
  say "  publish as is:     RESUME=1 ./deploy/amd/finalize_partial.sh   (marked PARTIAL, no evaluation score)"
  exit 1
fi

IP=$(curl -s -4 ifconfig.me || hostname -I | awk '{print $1}')
say "done. On your PC, in the CROMO folder, run:"
echo "    scp -r root@${IP}:$(pwd)/data/recorded ./data/"
say "then connect Evolus to http://${IP}:8000/v1 (docs/EVOLUS_SETUP.md step 4), and DESTROY the droplet when finished."
