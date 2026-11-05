# Sprint 3 — integrated backend release checklist

This checklist applies to `sprint3-merge` with one Alembic head
`0006_schedule_group_fk`. Never upgrade a real or shared PostgreSQL database
without a backup and a deployment plan.

## Pre-merge gates

- [ ] Every commit 1–4 change is pushed to `sprint3-merge` and reviewed.
- [ ] GitHub Actions `PostgreSQL migrations and integration tests` succeeds.
- [ ] GitHub Actions `Docker Compose smoke test` succeeds.
- [ ] No pytest tests unexpectedly `SKIPPED` (PostgreSQL integration tests use `TEST_DATABASE_URL`).
- [ ] Alembic has **one** head: `0006_schedule_group_fk`.
- [ ] Test the upgrade from clean DB, `0004_schedule`, and `0004_university` in isolated PostgreSQL schemas.
- [ ] CI validates `/health`, `/openapi.json`, creation of tables, and `seed.py`.
- [ ] Review code and migration diff, especially historical data compatibility.

## Migration safety and legacy data

`0006` is an *expand/backfill* migration. It retains old `group_key` and text
snapshots in `schedule_entries`, and the old `group_key` in `staff_schedule_groups`.
Unresolved rows remain with `study_group_id IS NULL`. The new Schedule API
operates on canonical IDs and will not serve these unmigrated rows.

After testing the migration on a copy of real data, review:

```sql
SELECT id, university, faculty, study_program, study_group, group_key
FROM schedule_entries WHERE study_group_id IS NULL;

SELECT staff_id, group_key
FROM staff_schedule_groups WHERE study_group_id IS NULL;
```

Never assign an ambiguous legacy key to an arbitrary group. Get the missing
university/program context or resolve the record manually with an audit trail.
Do not remove the legacy columns until every user-facing path and historical
record is migrated and the team agrees on the data-retention policy.

## Local Docker demonstration

Check your `.env` (never commit it). It must include a strong `POSTGRES_PASSWORD`
and distinct `JWT_SECRET`; `.env.example` is only a template. For passwords
containing URL-special characters, use URI-encoding before interpolating
`DATABASE_URL` in Compose (or adapt the configuration to construct connection
strings safely).

```bash
docker compose config --quiet
docker compose up -d --build
docker compose ps
docker compose exec backend alembic heads
docker compose exec backend alembic upgrade head
docker compose exec backend python seed.py
curl -fsS http://127.0.0.1:8000/health
```

The `backend` and `db` containers are separate; Docker's `db` hostname is
not your host machine's `localhost`. The Compose volume preserves data after
`docker compose down`. **Never run `docker compose down -v` on data that you
need to retain.** The `/health` endpoint only checks process response, not
schema completeness or correct business logic.

## Production deployment notes

- Confirm database backup and restore procedure before migration.
- Run migrations as an explicit deployment stage, not on every web-worker startup.
- This is not a zero-downtime rollout. If old and new API versions coexist,
  plan an expand/dual-read/contract strategy; otherwise schedule a maintenance
  window and verify rollback readiness.
- Restrict network access, terminate TLS in a gateway/reverse proxy, secure
  secrets, and set `ENVIRONMENT=production`, `DEBUG=false`.
- Provide idempotent initial-data management separately from read-only `GET`.
- **Remaining product limitation:** textual AI audience targeting does not
  always distinguish duplicate group names between institutions. A future
  domain change should use canonical entity IDs for audience targeting.

## PR process for the next sprint

1. Before work: agree on shared ORM models, APIs and ownership; record an ADR
   for common decisions like canonical `StudyGroup.id`.
2. Open a feature branch from latest `develop`, not another feature branch.
3. Keep PRs focused and small; separate migrations from unrelated features.
4. Use branch protection: required review and both CI checks on `develop`.
5. Merge upstream shared contracts before features that depend on them.
6. Run data migration tests, not only ORM `create_all()` tests.
