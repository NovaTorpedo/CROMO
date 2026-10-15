#!/usr/bin/env bash
# One-shot AMD session on the MI300X droplet (AMD Developer Cloud, "vLLM" Quick Start image, Docker installed).
#
#   git clone https://github.com/NovaTorpedo/CROMO.git && cd CROMO
#   export VLLM_API_KEY=$(openssl rand -hex 24); echo "$VLLM_API_KEY"   # keep it: Evolus needs it
#   ./deploy/amd/session.sh
#
# What it does (about 30-45 min, most of it the benchmark):
#   1. firewall (SSH + vLLM ports, API-key protected)
#   2. starts reasoner / vision / embeddings with vLLM on the GPU and waits until healthy
#   3. builds the CROMO evaluation container and runs it next to the GPU (host network, no internet hop):
#      scripts/check_amd.py -> scripts/benchmark_amd.py (ingest, investigate all, eval, latency, cost, replays, snapshot)
#   4. leaves the results in data/recorded/ - copy them to your PC with the scp command printed at the end
# The vLLM servers keep running so you can connect them to Evolus. DESTROY the droplet when done (it bills while it exists).
set -euo pipefail
cd "$(dirname "$0")/../.."
: "${VLLM_API_KEY:?Set VLLM_API_KEY first: export VLLM_API_KEY=\$(openssl rand -hex 24)}"
say() { printf '\033[1;33m[cromo]\033[0m %s\n' "$*"; }

say "1/4 firewall"
./deploy/amd/firewall.sh >/dev/null

say "2/4 starting the models (first start downloads ~80 GB of weights)"
./deploy/amd/serve_vllm.sh start
mkdir -p data/recorded
(rocm-smi --showproductname --showmeminfo vram --showuse > data/recorded/rocm-smi.txt 2>&1) || true

say "3/4 building the CROMO evaluation container"
umask 077
cat > .env.amd <<EOF
CROMO_PROVIDER=amd
CROMO_AMD_ROUTE=vllm
CROMO_REASONER_BASE_URL=http://127.0.0.1:8000/v1
CROMO_REASONER_API_KEY=${VLLM_API_KEY}
CROMO_REASONER_MODEL=${REASONER_MODEL:-Qwen/Qwen3-30B-A3B-Instruct-2507}
CROMO_VISION_BASE_URL=http://127.0.0.1:8001/v1
CROMO_VISION_API_KEY=${VLLM_API_KEY}
CROMO_VISION_MODEL=${VISION_MODEL:-Qwen/Qwen2.5-VL-7B-Instruct}
CROMO_EMBEDDINGS_BASE_URL=http://127.0.0.1:8002/v1
CROMO_EMBEDDINGS_API_KEY=${VLLM_API_KEY}
CROMO_EMBEDDINGS_MODEL=${EMBED_MODEL:-BAAI/bge-m3}
CROMO_STRUCTURED_OUTPUT=json_schema
CROMO_MAX_CONCURRENCY=12
CROMO_EVOLUS_ENABLED=false
CROMO_HARDWARE_LABEL=AMD Instinct MI300X (192 GB HBM3), ROCm + vLLM, AMD Developer Cloud
EOF
COMPOSE="docker compose -f docker-compose.yml -f deploy/amd/compose.amd.yml --profile eval"
$COMPOSE build eval

say "4/4 check + benchmark (records every investigation for demo replay)"
$COMPOSE run --rm eval python scripts/check_amd.py || {
  say "check failed: look at the FAIL lines above; if structured output is the only problem, set CROMO_STRUCTURED_OUTPUT=json_object in .env.amd and rerun"; exit 1; }
$COMPOSE run --rm eval python scripts/benchmark_amd.py --rocm-smi data/recorded/rocm-smi.txt --concurrency 8
rm -f .env.amd

IP=$(curl -s -4 ifconfig.me || hostname -I | awk '{print $1}')
say "done. On your PC, in the CROMO folder, run:"
echo "    scp -r root@${IP}:$(pwd)/data/recorded ./data/"
say "then connect Evolus to http://${IP}:8000/v1 (docs/EVOLUS_SETUP.md step 4), and DESTROY the droplet when finished."
