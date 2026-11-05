# MYUNI-119/120/121/122 + Telegram: branch from develop only

Source: `Crio9/University`, `develop` at commit `39f03f9ae0251f456e6db5f449dde586957a6446`. The separate `sprint3` branch (`7bd6957`) is **not included**.

## Files

- `app/models/schedule.py` — ORM table `schedule_entries`, `staff_schedule_groups` and constraints.
- `alembic/versions/0004_schedule.py` — new Alembic revision based on **0003_ai_audience**, not on sprint3.
- `app/schemas/schedule.py` — request/response Pydantic validation.
- `app/services/schedule.py` — permission checks, group identity, date/week bounds, move/cancel transitions.
- `app/api/schedule.py` — endpoints and admin grant of staff permissions.
- `app/api/router.py`, `app/models/__init__.py` — register the new code.
- `app/core/config.py`, `app/services/auth.py`, `app/schemas/auth.py`, `scripts/manage_roles.py` — security; public registration is limited to student/teacher, admin is bootstrapped from CLI, privileged roles by operator CLI only.
- `Dockerfile`, `compose.yaml`, `.dockerignore`, `docs/docker-backend-defense.md` — repeatable local demo with PostgreSQL 16, named volume, readiness and explicit migrations/seed.
- `app/services/telegram_source.py` — up to 15 pages with validated `?before=` pagination, max 300 text posts/channel, no arbitrary URL redirects.
- `app/services/telegram_storage.py` — batched idempotent inserts (100 rows/batch).
- `app/schemas/telegram_ingest.py`, `app/api/telegram_ingest.py` — up to 1000 JSON posts, up to 20 channels, no more than 3 concurrent fetches; max 100 auto-classified on request, remaining raw items stay `pending`.

## Schedule endpoints

- `GET /api/v1/schedule/me?date=2026-11-04` — current student's schedule on a specific day.
- `GET /api/v1/schedule/me?week=2026-11-04` — Mon–Sun week containing the date.
- `GET /api/v1/schedule/group?university=...&faculty=...&study_program=...&study_group=...&date=...` — scoped staff/admin view.
- `POST /api/v1/schedule` — staff/admin create (requires matching group grant for staff).
- `PATCH /api/v1/schedule/{id}` — staff/admin edit, move and cancel.
- `POST /api/v1/schedule/access/grant` — admin grants staff access to specified group context.

### POST /schedule JSON

```json
{
  "university": "ДГТУ", "faculty": "ФИСТ", "study_program": "ПМИ", "study_group": "ИВТ-31",
  "subject": "Программирование", "room": "301", "teacher": "Иванов И.И.",
  "starts_at": "2026-11-06T09:00:00+03:00", "ends_at": "2026-11-06T10:30:00+03:00"
}
```

### PATCH /schedule/{id} JSON

```json
{"status":"MOVED", "starts_at":"2026-11-07T09:00:00+03:00", "ends_at":"2026-11-07T10:30:00+03:00"}
```

To cancel: `{"status":"CANCELLED"}`. Cancelled entries remain visible and are immutable.

Time zone is **Europe/Moscow**, UTC offsets are mandatory. Incomplete student context returns `409 PROFILE_INCOMPLETE`. Role violation returns `403`. Data are sorted by the applicable original/new start time.

## Tests (run in your full checkout)

```bash
python -m pytest -q tests/test_auth.py tests/test_sprint3_security.py
python -m pytest -q tests/test_sprint3_schedule_unit.py tests/test_sprint3_telegram_bulk.py
python -m pytest -q
```

`tests/test_sprint3_schedule_pg.py` needs `TEST_DATABASE_URL` for an isolated PostgreSQL schema; it skips without it.

```bash
alembic current
alembic heads
alembic upgrade head
python seed.py
```

For Docker: follow `docs/docker-backend-defense.md`. Run `docker compose config` before `docker compose up -d --build` and verify `curl http://127.0.0.1:8000/health`. Note Docker startup does **not** automatically apply migrations.

## Important for Tech Lead merging another developer's `sprint3`

1. `sprint3` already contains `0004_university` based on `0003_ai_audience`.
2. This independent develop-based branch contains **another head** `0004_schedule` based on the same parent. They must be reconciled with an Alembic merge revision (or by revising the schedule migration onto `0004_university` before merging).
3. This schedule stores a `group_key` based on legacy `(university, faculty, study_program, study_group)` from `StudentProfile`. The new `StudyGroup` table is not imported here. During integration, backfill `study_group_id` into Schedule and staff grant tables, add foreign keys, preserve original data, and then migrate the APIs to canonical ID. Do not silently drop or combine groups with identical names.
4. Before branch integration, verify existing Sprint 2 ingestion, AI, feed, and profile tests again.
5. Confirm accepted rescheduling policy: original+new day visibility, cancelled rows remain, and Staff must have explicit permission. These are product decisions, not direct consequences of SQLAlchemy.

## Telegram limitations

HTML previews are not guaranteed to expose a channel's full history and may return fewer text posts than requested. Media-only posts are skipped. Server-side restrictions, rate limits and blocked previews remain possible. Use the `/api/v1/ingest/import` JSON fallback for extracted messages. Large syncs auto-queue at most 100 pending items for classification; the rest stay in RawContent with `pending` and can be processed using `/api/v1/ingest/process-pending?limit=1000` in repeated batches. Keep the AI key empty for ingestion-only testing; no external model calls will be made.
