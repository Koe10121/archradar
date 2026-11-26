FROM python:3.12-slim

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:0.6 /uv /usr/local/bin/uv

COPY pyproject.toml ./
RUN uv sync --no-dev --no-install-project

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app

EXPOSE 8000

CMD ["uv", "run", "--no-dev", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
