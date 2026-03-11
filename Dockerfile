# syntax=docker/dockerfile:1
FROM python:3.14-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy project
COPY linear_bot ./linear_bot
COPY pyproject.toml ./

# Install runtime deps via pip (from pyproject constraints)
RUN python -m venv /opt/venv \
    && . /opt/venv/bin/activate \
    && pip install --upgrade pip setuptools wheel \
    && pip install aiogram==3.13.1 httpx==0.27.2 APScheduler==3.10.4 pytz==2024.1 pydantic==2.9.2 PyYAML==6.0.2

ENV PATH=/opt/venv/bin:$PATH

# Default data/config locations inside container
ENV LINEAR_BOT_CONFIG=/config/config.toml \
    LINEAR_BOT_DATA=/data

# Entrypoint
CMD ["python", "-m", "linear_bot"]
