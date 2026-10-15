#!/usr/bin/env bash
# CROMO - serve the model roles with vLLM on ONE AMD Instinct MI300X (ROCm).
#
#   export VLLM_API_KEY="$(openssl rand -hex 24)"   # keep it secret; same value goes into CROMO's .env and Evolus
#   ./serve_vllm.sh start      # start the servers of the chosen PROFILE and wait until healthy
#   ./serve_vllm.sh status     # health + loaded models + GPU memory
#   ./serve_vllm.sh logs       # tail logs
#   ./serve_vllm.sh stop       # stop all servers (the droplet keeps billing until you DESTROY it)
#
# PROFILE (default: gemma)
#   gemma    :8000 Gemma 4 26B-A4B  = REASONER + VISION (one multimodal model, tool calling)    0.70 of HBM
#            :8002 bge-m3           = EMBEDDINGS                                               0.08
#   qwen     :8000 Qwen3-30B-A3B    = REASONER   :8001 Qwen2.5-VL-7B = VISION   :8002 bge-m3
#   compare  gemma profile + :8001 Qwen2.5-VL-7B (0.15) so scripts/compare_models.py can measure Gemma
#            against the alternative on the same scans (A/B quality test)
#
# Every endpoint requires the API key (an unprotected vLLM endpoint is open to anyone).
set -euo pipefail

CMD="${1:-start}"
: "${VLLM_API_KEY:?Set VLLM_API_KEY first (e.g. export VLLM_API_KEY=\$(openssl rand -hex 24))}"
PROFILE="${PROFILE:-gemma}"

GEMMA_MODEL="${GEMMA_MODEL:-google/gemma-4-26B-A4B-it}"
QWEN_REASONER="${QWEN_REASONER:-Qwen/Qwen3-30B-A3B-Instruct-2507}"
QWEN_VISION="${QWEN_VISION:-Qwen/Qwen2.5-VL-7B-Instruct}"
EMBED_MODEL="${EMBED_MODEL:-BAAI/bge-m3}"
GEMMA_UTIL="${GEMMA_UTIL:-0.70}"
EMBED_UTIL="${EMBED_UTIL:-0.08}"
MAXLEN="${MAXLEN:-32768}"
# Gemma 4 on ROCm uses the Triton attention backend (bidirectional attention over image tokens)
GEMMA_ENV=(-e VLLM_ATTENTION_BACKEND="${VLLM_ATTENTION_BACKEND:-TRITON_ATTN}")
# image budget: 1120 soft tokens per page = best for OCR / small text / handwriting
GEMMA_MM_KWARGS="${GEMMA_MM_KWARGS:-}"
[ -n "$GEMMA_MM_KWARGS" ] || GEMMA_MM_KWARGS='{"max_soft_tokens": 1120}'
# optional custom tool chat template (Gemma 4's own template already supports tools), e.g.
#   GEMMA_TOOL_TEMPLATE=examples/tool_chat_template_gemma4.jinja
GEMMA_TOOL_TEMPLATE="${GEMMA_TOOL_TEMPLATE:-}"
IMAGE="${VLLM_IMAGE:-vllm/vllm-openai-rocm:latest}"
HF_CACHE="${HF_CACHE:-/root/.cache/huggingface}"

say() { printf '\033[1;33m[cromo]\033[0m %s\n' "$*"; }

launch() { # name port model util [docker-env...] -- [vllm args...]
  local name=$1 port=$2 model=$3 util=$4; shift 4
  local envs=()
  while [ $# -gt 0 ] && [ "$1" != "--" ]; do envs+=("$1"); shift; done
  [ "${1:-}" = "--" ] && shift
  say "starting $name ($model) on :$port with $IMAGE"
  docker rm -f "cromo-$name" >/dev/null 2>&1 || true
  docker run -d --name "cromo-$name" --network host --ipc=host --group-add video --cap-add SYS_PTRACE \
    --security-opt seccomp=unconfined --device /dev/kfd --device /dev/dri \
    -v "$HF_CACHE:/root/.cache/huggingface" -e HF_TOKEN="${HF_TOKEN:-}" "${envs[@]}" \
    "$IMAGE" --model "$model" --host 0.0.0.0 --port "$port" --api-key "$VLLM_API_KEY" \
    --gpu-memory-utilization "$util" "$@" >/dev/null
}

wait_healthy() { # port name
  local port=$1 name=$2
  say "waiting for $name on :$port (first start downloads the weights; this can take several minutes)"
  for _ in $(seq 1 180); do
    if curl -sf -H "Authorization: Bearer $VLLM_API_KEY" "http://127.0.0.1:$port/v1/models" >/dev/null; then
      say "$name is up"; return 0
    fi
    if ! docker ps --format '{{.Names}}' | grep -q "^cromo-$name$"; then
      say "ERROR: container cromo-$name stopped - last log lines:"; docker logs --tail 30 "cromo-$name" 2>&1 || true; return 1
    fi
    sleep 10
  done
  say "ERROR: $name did not become healthy - run: $0 logs"; return 1
}

start_gemma() {
  launch gemma 8000 "$GEMMA_MODEL" "$GEMMA_UTIL" "${GEMMA_ENV[@]}" -- \
    --max-model-len "$MAXLEN" --limit-mm-per-prompt '{"image": 2}' --mm-processor-kwargs "$GEMMA_MM_KWARGS" \
    --enable-auto-tool-choice --tool-call-parser gemma4 --reasoning-parser gemma4 \
    ${GEMMA_TOOL_TEMPLATE:+--chat-template "$GEMMA_TOOL_TEMPLATE"}
  wait_healthy 8000 gemma
}

start_embeddings() {
  launch embeddings 8002 "$EMBED_MODEL" "$EMBED_UTIL" --
  wait_healthy 8002 embeddings
}

case "$CMD" in
  start)
    # switching profiles reuses ports 8000-8002: remove every CROMO server first
    docker rm -f cromo-gemma cromo-reasoner cromo-vision cromo-embeddings >/dev/null 2>&1 || true
    case "$PROFILE" in
      gemma)
        start_gemma; start_embeddings ;;
      compare)
        start_gemma
        launch vision 8001 "$QWEN_VISION" "${QWEN_VISION_UTIL:-0.15}" -- --max-model-len 16384
        wait_healthy 8001 vision
        start_embeddings ;;
      qwen)
        launch reasoner 8000 "$QWEN_REASONER" "${QWEN_UTIL:-0.55}" -- --max-model-len "$MAXLEN" \
          --enable-auto-tool-choice --tool-call-parser hermes
        wait_healthy 8000 reasoner
        launch vision 8001 "$QWEN_VISION" "${QWEN_VISION_UTIL:-0.25}" -- --max-model-len 16384
        wait_healthy 8001 vision
        start_embeddings ;;
      *) echo "unknown PROFILE=$PROFILE (gemma | compare | qwen)"; exit 2 ;;
    esac
    say "all servers of profile '$PROFILE' are up. GPU memory:"
    (command -v rocm-smi >/dev/null && rocm-smi --showmeminfo vram) || true
    ;;
  status)
    for p in 8000 8001 8002; do
      printf ':%s ' "$p"; curl -s -H "Authorization: Bearer $VLLM_API_KEY" "http://127.0.0.1:$p/v1/models" | head -c 200; echo
    done
    (command -v rocm-smi >/dev/null && rocm-smi --showmeminfo vram --showuse) || true
    ;;
  logs)
    for n in gemma reasoner vision embeddings; do
      docker ps -a --format '{{.Names}}' | grep -q "^cromo-$n$" && { echo "== $n"; docker logs --tail 40 "cromo-$n" 2>&1; }
    done; true
    ;;
  stop)
    docker rm -f cromo-gemma cromo-reasoner cromo-vision cromo-embeddings >/dev/null 2>&1 || true
    say "stopped. Remember: a powered-off droplet still bills - DESTROY it in the AMD Developer Cloud console when done."
    ;;
  *) echo "usage: [PROFILE=gemma|compare|qwen] $0 start|status|logs|stop"; exit 2 ;;
esac
