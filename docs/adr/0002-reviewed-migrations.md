# 0002 — Reviewed migrations that run before the rollout

Status: accepted

## Context

The schema changes with the application, and in production the database
already holds data when a change arrives. A deployment on ECS replaces tasks
gradually, so for a while the old and the new version run side by side
against the same database.

## Decision

- Schema changes are **Alembic migrations**. `alembic revision --autogenerate`
  writes a draft; the draft is reviewed and usually edited by hand before it
  is committed.
- Migrations **never import application code**. A migration has to produce the
  same result years later, whatever the models look like by then; logic it
  needs is copied into it and frozen (e.g. the skill key in `0003_skill_key`).
- **Data is migrated, not guessed at.** When existing rows cannot be migrated
  unambiguously, the migration stops with an explanation instead of picking
  a winner: `0003` refuses to run while two skills would get the same key.
- **CI checks** that the migrations and the models describe the same schema
  (`alembic check`); migrations with data handling have their own tests
  (`tests/test_migrations.py`).
- **Migrations run once per deployment, before the rollout**, as a one-off
  task of the new image (`alembic upgrade head`), never at application start.
  Locally the `migrate` service of `docker-compose.yml` does the same.
- Because the old version keeps running during the rollout, a migration must be
  **backwards compatible with the version before it**: add columns nullable or
  with a default, and remove or rename in a later release (expand, then
  contract).

## Alternatives

- **Running migrations at application start**: every task would race to
  migrate, and a failing migration would show up as crashing tasks.
- **`Base.metadata.create_all()`**: fine for tests, but it cannot change an
  existing schema or move data.

## Consequences

- Breaking changes take two releases.
- A failed migration stops the deployment before any task runs the new code;
  since PostgreSQL runs DDL in transactions, the database is left unchanged.
