FROM python:3.12.8-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /workspace

RUN groupadd --system ostrading && useradd --system --gid ostrading --home-dir /workspace ostrading

COPY pyproject.toml ./pyproject.toml
COPY app ./app
RUN pip install --no-cache-dir .

USER ostrading
