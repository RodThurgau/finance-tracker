# finance-tracker

A local-first personal finance tracker that ingests ING (DE) and PayPal CSV exports into a SQLite database, with a React UI for browsing, categorizing, tagging, and exporting transactions.

See [CLAUDE.md](CLAUDE.md) for full architecture and conventions, and [CHANGELOG.md](CHANGELOG.md) for what changed and what is still open.

## Starting the app (e.g. after a reboot)

Nothing runs automatically — after a PC restart, both servers need to be started manually. Open two terminals:

```powershell
# Terminal 1 — backend (also runs the DB backup + migrations on startup)
cd backend
uv run uvicorn main:app --reload --port 8000

# Terminal 2 — frontend
cd frontend
npm run dev
```

Then open the site in your browser: **http://localhost:5173**

Leave both terminals running while you use the app; closing either one stops that half of the app. To stop, press `Ctrl+C` in each terminal.

## Development

```bash
# Backend
cd backend
uv sync
uv run alembic upgrade head          # also runs automatically on startup
uv run uvicorn main:app --reload --port 8000

# Tests
uv run pytest

# Frontend
cd frontend
npm install
npm run dev
```

## Backups and restore

On every backend startup, `backup.py` snapshots `data/finance.db` into `backups/finance-YYYYMMDD-HHMMSS.db` before any migration runs. Startup aborts if this snapshot fails, so a database is never migrated unbacked. Retention keeps the 20 most recent snapshots, plus the first snapshot of each day for the last 30 days; older snapshots are pruned automatically.

To restore from a snapshot:

1. Stop the backend server.
2. Pick a snapshot from `backups/` (most recent, or an earlier one if you need to undo something further back).
3. Copy it over the live database: `cp backups/finance-<timestamp>.db data/finance.db`.
4. Restart the server.
