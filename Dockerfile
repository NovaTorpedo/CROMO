# syntax=docker/dockerfile:1
# CROMO - one container: FastAPI backend + built React frontend. Non-root, health-checked.

# ---- frontend build -----------------------------------------------------------
FROM node:22-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---- runtime ----------------------------------------------------------------------
FROM python:3.12-slim AS app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 CROMO_ROOT=/app PORT=8000
RUN useradd --create-home --uid 10001 cromo
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/cromo backend/cromo
COPY archive archive
COPY fixtures fixtures
COPY data/recorded data/recorded
COPY data/evolus_cache data/evolus_cache
COPY scripts/check_amd.py scripts/check_amd.py
COPY --from=web /web/dist frontend/dist
RUN mkdir -p data/runtime && chown -R cromo:cromo /app/data
USER cromo
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8000\")}/api/health', timeout=4)" || exit 1
CMD ["sh", "-c", "exec python -m uvicorn cromo.api:app --app-dir backend --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --no-server-header"]

# ---- evaluation / benchmark image (adds the answer key; never used to serve the app) ----
FROM app AS eval
USER root
COPY eval eval
COPY scripts scripts
RUN chown -R cromo:cromo /app/eval /app/scripts
USER cromo
CMD ["python", "eval/run_eval.py"]
