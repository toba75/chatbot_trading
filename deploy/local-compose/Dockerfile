FROM python:3.12.8-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /workspace

RUN groupadd --system ostrading && useradd --system --gid ostrading --home-dir /workspace ostrading

COPY pyproject.toml ./pyproject.toml
COPY uv.lock ./uv.lock
COPY app ./app
RUN pip install --no-cache-dir uv==0.11.28 && uv sync --frozen --no-dev

ENV PATH="/workspace/.venv/bin:${PATH}"

USER ostrading
