# Hevy Dashboard

A FastAPI app that syncs your Hevy workouts and shows a dashboard. Includes a background job to periodically fetch latest workouts. Dockerized for easy run.

## Quick start

1. Create `.env` from example and set your API key:

```bash
cp .env.example .env
# edit .env and set HEVY_API_KEY
```

2. Run with Docker:

```bash
docker compose up --build
```

Then open http://localhost:8000

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Notes
- Database: SQLite (`hevy.db`) via SQLModel/SQLAlchemy (async aiosqlite driver)
- Background sync: APScheduler runs every 15 minutes
- Extend `app/services/hevy_client.py` with additional endpoints as needed
