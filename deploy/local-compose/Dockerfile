FROM ghcr.io/astral-sh/uv@sha256:0f36cb9361a3346885ca3677e3767016687b5a170c1a6b88465ec14aefec90aa AS uv-binary

FROM docker:27.5.1-cli@sha256:851f91d241214e7c6db86513b270d58776379aacc5eb9c4a87e5b47115e3065c AS docker-cli

FROM python:3.12.8-slim-bookworm@sha256:2199a62885a12290dc9c5be3ca0681d367576ab7bf037da120e564723292a2f0 AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /workspace

COPY --from=uv-binary /uv /uvx /bin/

COPY pyproject.toml ./pyproject.toml
COPY uv.lock ./uv.lock
RUN uv sync --frozen --no-dev --no-install-project

COPY app ./app
COPY ost_gate ./ost_gate
COPY deploy/postgres/migrations ./deploy/postgres/migrations
RUN uv sync --frozen --no-dev --offline --no-build-isolation

FROM python:3.12.8-slim-bookworm@sha256:2199a62885a12290dc9c5be3ca0681d367576ab7bf037da120e564723292a2f0 AS runtime

ARG OSTRADING_IMAGE_REVISION
ARG OSTRADING_POSTGRES_SCHEMA_VERSION

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/workspace/.venv/bin:${PATH}"

WORKDIR /workspace

RUN groupadd --system --gid 31000 ostrading \
    && useradd --system --gid ostrading --home-dir /workspace ostrading \
    && mkdir -p \
        /workspace/data/corpus \
        /workspace/data/experiments \
        /workspace/data/environments/development \
        /workspace/data/environments/test \
        /workspace/data/environments/production \
        /workspace/config/secrets/development \
        /workspace/config/secrets/test \
        /workspace/config/secrets/production \
    && chown -R ostrading:ostrading /workspace/data

COPY --from=builder --chown=ostrading:ostrading /workspace/.venv /workspace/.venv
COPY --chown=ostrading:ostrading app ./app
COPY --chown=ostrading:ostrading ost_gate ./ost_gate
COPY --chown=ostrading:ostrading deploy/postgres/migrations ./deploy/postgres/migrations

LABEL org.opencontainers.image.version="0.1.0-m013-fastapi-schema-${OSTRADING_POSTGRES_SCHEMA_VERSION}"
LABEL org.opencontainers.image.revision="${OSTRADING_IMAGE_REVISION}"
LABEL org.ostrading.postgres-schema-version="${OSTRADING_POSTGRES_SCHEMA_VERSION}"

USER ostrading

FROM runtime AS orchestrator-api

ENTRYPOINT ["api"]

FROM runtime AS worker-documents

ENV DOCKER_HOST="unix:///var/run/ocr-docker/docker.sock"

COPY --from=docker-cli /usr/local/bin/docker /usr/local/bin/docker
COPY --chown=ostrading:ostrading config/ocrmypdf-image.json ./config/ocrmypdf-image.json
COPY --chown=ostrading:ostrading config/docling-assets.native.json ./config/docling-assets.native.json
COPY --chown=ostrading:ostrading config/docling-assets.granite.json ./config/docling-assets.granite.json

ENTRYPOINT ["python", "-m", "app.source_processing.adapters.worker_runtime"]

FROM runtime AS worker-projection

ENTRYPOINT ["python", "-m", "app.knowledge_access.adapters.worker_runtime"]

FROM runtime AS generic-service
