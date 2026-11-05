# MyUni Backend Defense: Docker Compose

## Setup

1. `cp .env.example .env` (only when no existing .env is present).
2. Edit `.env`: set `POSTGRES_PASSWORD` to a local nontrivial password, and `JWT_SECRET` to `openssl rand -hex 32` output. For demo use `ENVIRONMENT=development`, `DEBUG=false`.
   `DATABASE_URL`/`ALEMBIC_DATABASE_URL` in `.env` describe local host development;
   Compose overrides the hosts with `db` automatically.
3. `docker compose up -d --build` (starts PostgreSQL + backend; waits for DB readiness).
4. `docker compose exec backend alembic upgrade head` (EXPLICIT; only after migrations from other developers are merged).
5. `docker compose exec backend python seed.py` (EXPLICIT; demo data, not run automatically).
6. `docker compose exec -e ADMIN_BOOTSTRAP_PASSWORD backend python -m scripts.manage_roles bootstrap-admin --email admin@example.test` requires `ADMIN_BOOTSTRAP_PASSWORD` set in your shell. Do not use demo credentials in production.
7. Open http://127.0.0.1:8000/docs (or configured BACKEND_PORT).

If the DB is initialized, `docker compose down` does NOT delete the named volume; use `docker compose down -v` ONLY when intending to permanently erase local PostgreSQL data.

`GET /health` signals backend process responsiveness, not migration completion.
NVIDIA_API_KEY can remain empty: ingestion stores pending RawContent until configured, but schedule, appeals and auth work normally. After providing an API key, use the existing process-pending API for queued content.

For public deployment: set `ENVIRONMENT=production`, `DEBUG=false`, secure random `JWT_SECRET`, TLS + gateway/proxy, strong DB password and private network exposure configuration. This compose.yaml binds the API to loopback on purpose (local defense only).
