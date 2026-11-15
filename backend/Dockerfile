# syntax=docker/dockerfile:1
FROM python:3.12-slim-bookworm AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    TIKTOKEN_CACHE_DIR=/opt/tiktoken \
    STORAGE_DIR=/data/storage \
    PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir uv==0.13.6 \
    && useradd --system --uid 10001 --create-home app \
    && mkdir -p /data/storage && chown app:app /data/storage
WORKDIR /app
COPY pyproject.toml uv.lock ./

FROM base AS dev
RUN uv sync --frozen --no-install-project \
    && python -c "import tiktoken; tiktoken.get_encoding('cl100k_base')"
COPY . .
USER app
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]

FROM base AS prod
RUN uv sync --frozen --no-dev --no-install-project \
    && python -c "import tiktoken; tiktoken.get_encoding('cl100k_base')"
COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
USER app
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips=*"]
