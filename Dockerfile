# Udyam Digital API (Cloud Run). Build context = repo root:  docker build -t udyam-api --build-arg BUILD_SHA=$(git rev-parse --short HEAD) .
# Synthetic data is baked in (PLAN Phase 8). The propensity model is trained at build time (the .joblib is git-ignored), so the image is reproducible.
FROM python:3.12-slim

ARG BUILD_SHA=dev
ENV PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy BUILD_SHA=${BUILD_SHA} PORT=8080 \
    APP_ENV=prod PATH="/srv/api/.venv/bin:${PATH}"

RUN apt-get update && apt-get install -y --no-install-recommends libglib2.0-0 && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv==0.13.7 && useradd --create-home --uid 10001 app

WORKDIR /srv/api
COPY api/pyproject.toml api/uv.lock ./
RUN uv sync --frozen --no-dev

COPY api/app ./app
COPY api/config ./config
COPY data/raw /srv/data/raw
COPY data/derived /srv/data/derived
COPY scripts/train_propensity.py /srv/scripts/train_propensity.py
RUN python /srv/scripts/train_propensity.py > /tmp/train.log && tail -3 /tmp/train.log && rm /tmp/train.log \
    && chown -R app:app /srv

USER app
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request,os;urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8080')+'/health')"
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080} --proxy-headers --forwarded-allow-ips='*'"]
