# =====================================================================
# Backend UTE-VICE — imagen multietapa
# =====================================================================
ARG PYTHON_VERSION=3.13

# ------------------------------ base ---------------------------------
FROM python:${PYTHON_VERSION}-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app/src \
    TZ=America/Guayaquil

WORKDIR /app

# libpq: cliente PostgreSQL. build-essential/libffi: compilacion de argon2-cffi.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential libpq-dev libffi-dev tzdata curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./

# ------------------------- development -------------------------------
FROM base AS development

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip && \
    pip install -e ".[dev,ldap]"

COPY . .
RUN mkdir -p /app/storage/reports

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--reload-dir", "/app/src"]

# -------------------------- production -------------------------------
FROM base AS production

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip && \
    pip install ".[ldap]"

COPY . .

# Usuario sin privilegios: el proceso nunca corre como root.
RUN groupadd --system --gid 1001 ute \
    && useradd --system --uid 1001 --gid ute --create-home ute \
    && mkdir -p /app/storage/reports \
    && chown -R ute:ute /app
USER ute

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
