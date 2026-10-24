FROM node:22-bookworm-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/opt/venv/bin:${PATH}" \
    CDA_CLOUD_MODE=1 \
    PORT=8000

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-venv \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir 'pytest>=7,<9' \
    && npm install --global @openai/codex@0.143.0 \
    && npm_config_ignore_scripts=false npm install --global @github/copilot \
    && groupadd --system arena \
    && useradd --system --gid arena --home-dir /tmp/codex-home arena

COPY --chown=arena:arena . /app

USER arena
EXPOSE 8000
CMD ["sh", "-c", "exec python web/server.py --host 0.0.0.0 --port ${PORT:-8000}"]

