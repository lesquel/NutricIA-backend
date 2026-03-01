# NutricIA Backend

Open-source AI-powered calorie tracker backend built with **FastAPI** + **PostgreSQL**.

## Stack

- **FastAPI** — async Python web framework
- **SQLAlchemy 2.0** — async ORM with PostgreSQL (asyncpg)
- **Alembic** — database migrations
- **Pydantic v2** — data validation & settings
- **AI Providers** — Gemini 2.0 Flash / GPT-4o (configurable)
- **uv** — fast Python package manager

## Setup

```bash
# Install dependencies
uv sync

# Copy env file and configure
cp .env.example .env
# Edit .env with your database URL, API keys, etc.

# Run database migrations
uv run alembic upgrade head

# Start dev server
uv run uvicorn app.main:app --reload --port 8000
```

## API Docs

Once running, visit: `http://localhost:8000/docs`

## Quality & Tests

```bash
# Format + lint
uv run ruff format .
uv run ruff check .

# Type checks
uv run mypy app/ --ignore-missing-imports

# Tests
uv run pytest
```

## Migration Notes

- Always run migrations on a clean database in CI-like scenarios:

```bash
uv run alembic upgrade head
```

- If your local database is out of sync during development, reset it before retesting migrations.

## Project Structure

```
app/
├── main.py           # FastAPI app factory, lifespan, middleware
├── config.py         # pydantic-settings configuration
├── database.py       # async SQLAlchemy engine & session
├── dependencies.py   # get_db, get_current_user (JWT)
│
├── auth/             # OAuth authentication (Google/Apple)
├── meals/            # Meal CRUD + AI food analysis
├── analytics/        # Daily/weekly/monthly stats aggregation
├── habits/           # Habit Garden + Water tracker
└── users/            # Profile & settings management
```

## Features

- **Meal Scanning** — Upload a food photo → AI returns calories, macros, ingredients
- **Dual AI Provider** — Switch between Gemini and OpenAI via `AI_PROVIDER` env var
- **OAuth Login** — Google and Apple Sign-In
- **Analytics** — SQL-aggregated daily/weekly/monthly nutritional summaries
- **Habit Garden** — Gamified habit tracking with streaks and plant growth
- **Water Tracking** — Daily hydration logging

## Contributing (Backend)

- Follow root contribution guide: `../CONTRIBUTING.md`
- Keep changes scoped to one module when possible (`auth`, `meals`, `habits`, etc.)
- Update Alembic migration + related models together in the same PR
