# PlankTonne Server

FastAPI backend for measuring resin volume in live edge wood forms.

## Development

```bash
# Install dependencies
uv sync

# Run server
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run tests
uv run pytest

# Lint
uv run ruff check .
uv run ruff format .
uv run mypy app
```

## API

- `GET /health` - Health check
- `POST /v1/measure-boards` - Measure board areas from image and ROIs