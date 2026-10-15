#!/usr/bin/env bash
# Publish what an interrupted AMD benchmark measured, clearly marked PARTIAL (no evaluation score, no audit cost).
# Use only when there is no time left to finish it with: RESUME=1 ./deploy/amd/session.sh
#
#   ./deploy/amd/finalize_partial.sh            # primary (Gemma) run
#   TAG=qwen ./deploy/amd/finalize_partial.sh   # the optional reasoner A/B run
set -euo pipefail
cd "$(dirname "$0")/../.."
trap 'rm -f .env.amd' EXIT
umask 077
{
  echo "CROMO_PROVIDER=amd"
  echo "CROMO_AMD_ROUTE=vllm"
  echo "CROMO_EVOLUS_ENABLED=false"
  echo "CROMO_HARDWARE_LABEL=AMD Instinct MI300X (192 GB HBM3), ROCm + vLLM, AMD Developer Cloud"
} > .env.amd
COMPOSE="docker compose -f docker-compose.yml -f deploy/amd/compose.amd.yml --profile eval"
$COMPOSE run --rm eval python scripts/benchmark_amd.py --finalize-partial --rocm-smi data/recorded/rocm-smi.txt ${TAG:+--tag "$TAG"}
IP=$(curl -s -4 ifconfig.me || hostname -I | awk '{print $1}')
echo "Copy the results to your PC:  scp -r root@${IP}:$(pwd)/data/recorded ./data/"
