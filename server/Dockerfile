# ── Builder: installs Python deps into .venv ─────────────────────────────────
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# ── Runtime: lean image with only what's needed to run ───────────────────────
FROM python:3.12-slim AS runtime

# libgl1 required by OpenCV, libgomp1 by rembg/onnxruntime
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --shell /bin/bash app
WORKDIR /app

COPY --from=builder --chown=app:app /app/.venv /app/.venv

USER app
COPY --chown=app:app app/ ./app/

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

# Download rembg model at build time so the first request doesn't stall
RUN python -c "from rembg import new_session; new_session('isnet-general-use')"

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
