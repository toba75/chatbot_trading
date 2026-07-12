FROM python:3.12.8-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /workspace

COPY pyproject.toml ./pyproject.toml
COPY uv.lock ./uv.lock
COPY app ./app
COPY deploy/postgres/migrations ./deploy/postgres/migrations
RUN pip install --no-cache-dir uv==0.11.28 && uv sync --frozen --no-dev

FROM python:3.12.8-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/workspace/.venv/bin:${PATH}"

WORKDIR /workspace

RUN groupadd --system ostrading && useradd --system --gid ostrading --home-dir /workspace ostrading

COPY --from=builder --chown=ostrading:ostrading /workspace/.venv /workspace/.venv
COPY --chown=ostrading:ostrading app ./app
COPY --chown=ostrading:ostrading deploy/postgres/migrations ./deploy/postgres/migrations

LABEL org.opencontainers.image.version="0.1.0-m013-fastapi-schema-004"
LABEL org.ostrading.postgres-schema-version="004"

USER ostrading
