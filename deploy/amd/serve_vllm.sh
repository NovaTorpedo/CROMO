#!/usr/bin/env bash
# CROMO - serve all model roles with vLLM on ONE AMD Instinct MI300X (ROCm).
#
# Run on the AMD Developer Cloud GPU droplet (Ubuntu, Docker, ROCm). Usage:
#   export VLLM_API_KEY="$(openssl rand -hex 24)"   # keep it secret; put the same value in CROMO's .env
#   ./serve_vllm.sh start      # start reasoner (8000), vision (8001), embeddings (8002); waits until healthy
#   ./serve_vllm.sh status     # health + loaded models + GPU memory
#   ./serve_vllm.sh logs       # tail logs
#   ./serve_vllm.sh stop       # stop all servers (the droplet keeps billing until you DESTROY it)
#
# Every endpoint requires the API key (an unprotected vLLM endpoint is open to anyone).
# Memory plan on 192 GB HBM3: reasoner 0.55, vision 0.25, embeddings 0.08 of GPU memory (sum 0.88).
set -euo pipefail

CMD="${1:-start}"
: "${VLLM_API_KEY:?Set VLLM_API_KEY first (e.g. export VLLM_API_KEY=\$(openssl rand -hex 24))}"

REASONER_MODEL="${REASONER_MODEL:-Qwen/Qwen3-30B-A3B-Instruct-2507}"
VISION_MODEL="${VISION_MODEL:-Qwen/Qwen2.5-VL-7B-Instruct}"
EMBED_MODEL="${EMBED_MODEL:-BAAI/bge-m3}"
REASONER_UTIL="${REASONER_UTIL:-0.55}"
VISION_UTIL="${VISION_UTIL:-0.25}"
EMBED_UTIL="${EMBED_UTIL:-0.08}"
REASONER_MAXLEN="${REASONER_MAXLEN:-32768}"
VISION_MAXLEN="${VISION_MAXLEN:-16384}"
IMAGE="${VLLM_IMAGE:-vllm/vllm-openai-rocm:latest}"
HF_CACHE="${HF_CACHE:-/root/.cache/huggingface}"
LOGDIR=/tmp/cromo-vllm

say() { printf '\033[1;33m[cromo]\033[0m %s\n' "$*"; }

# Prefer the vLLM container that the AMD Developer Cloud "vLLM Quick Start" image already runs (named "rocm")
# when it uses host networking; otherwise run the official vLLM ROCm image ourselves with host networking.
mode() {
  if docker inspect rocm >/dev/null 2>&1 && [ "$(docker inspect -f '{{.HostConfig.NetworkMode}}' rocm)" = "host" ]; then
    echo exec
  else
    echo run
  fi
}

launch() { # name port model util extra-args...
  local name=$1 port=$2 model=$3 util=$4; shift 4
  local args=(--host 0.0.0.0 --port "$port" --api-key "$VLLM_API_KEY" --gpu-memory-utilization "$util" "$@")
  if [ "$(mode)" = exec ]; then
    say "starting $name ($model) on :$port inside container 'rocm'"
    docker exec -d -e VLLM_API_KEY rocm bash -lc "mkdir -p $LOGDIR && vllm serve $model ${args[*]} > $LOGDIR/$name.log 2>&1"
  else
    say "starting $name ($model) on :$port with $IMAGE"
    docker rm -f "cromo-$name" >/dev/null 2>&1 || true
    docker run -d --name "cromo-$name" --network host --ipc=host --group-add video --cap-add SYS_PTRACE \
      --security-opt seccomp=unconfined --device /dev/kfd --device /dev/dri \
      -v "$HF_CACHE:/root/.cache/huggingface" -e HF_TOKEN="${HF_TOKEN:-}" \
      "$IMAGE" --model "$model" "${args[@]}" >/dev/null
  fi
}

wait_healthy() { # port name
  local port=$1 name=$2
  say "waiting for $name on :$port (first start downloads the model weights; this can take several minutes)"
  for _ in $(seq 1 180); do
    if curl -sf -H "Authorization: Bearer $VLLM_API_KEY" "http://127.0.0.1:$port/v1/models" >/dev/null; then
      say "$name is up"; return 0
    fi
    sleep 10
  done
  say "ERROR: $name did not become healthy - run: $0 logs"; return 1
}

case "$CMD" in
  start)
    # reasoner first: it profiles memory alone, then the others fit into what is left
    launch reasoner 8000 "$REASONER_MODEL" "$REASONER_UTIL" --max-model-len "$REASONER_MAXLEN" \
      --enable-auto-tool-choice --tool-call-parser hermes
    wait_healthy 8000 reasoner
    launch vision 8001 "$VISION_MODEL" "$VISION_UTIL" --max-model-len "$VISION_MAXLEN"
    wait_healthy 8001 vision
    launch embeddings 8002 "$EMBED_MODEL" "$EMBED_UTIL"
    wait_healthy 8002 embeddings
    say "all roles up. GPU memory:"
    (command -v rocm-smi >/dev/null && rocm-smi --showmeminfo vram) || true
    ;;
  status)
    for p in 8000 8001 8002; do
      printf ':%s ' "$p"; curl -s -H "Authorization: Bearer $VLLM_API_KEY" "http://127.0.0.1:$p/v1/models" | head -c 200; echo
    done
    (command -v rocm-smi >/dev/null && rocm-smi --showmeminfo vram --showuse) || true
    ;;
  logs)
    if [ "$(mode)" = exec ]; then docker exec rocm bash -lc "tail -n 40 $LOGDIR/*.log"; else
      for n in reasoner vision embeddings; do echo "== $n"; docker logs --tail 40 "cromo-$n" 2>&1; done; fi
    ;;
  stop)
    if [ "$(mode)" = exec ]; then docker exec rocm bash -lc "pkill -f 'vllm serve' || true"; else
      docker rm -f cromo-reasoner cromo-vision cromo-embeddings >/dev/null 2>&1 || true; fi
    say "stopped. Remember: a powered-off droplet still bills - DESTROY it in the AMD Developer Cloud console when done."
    ;;
  *) echo "usage: $0 start|status|logs|stop"; exit 2 ;;
esac
