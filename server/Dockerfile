FROM python:3.12-slim

# Install system dependencies for OpenCV and Rembg
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd --create-home --shell /bin/bash app \
    && mkdir -p /app \
    && chown -R app:app /app

USER app
WORKDIR /app

# Copy dependency files
COPY --chown=app:app pyproject.toml ./

# Install Python dependencies
RUN pip install --no-cache-dir uv \
    && uv sync --no-install-project --frozen-lockfile

# Copy source code
COPY --chown=app:app . .

# Pre-download Rembg model during build
RUN uv run python -c "from rembg import new_session; new_session('isnet-general-use')"

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]