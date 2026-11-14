# 0001 — Async FastAPI with SQLAlchemy 2 and PostgreSQL

Status: accepted

## Context

The stack is set by the assignment: Python, FastAPI and SQLAlchemy. Open were
the database, and whether the code is synchronous or asynchronous. The
application runs as containers on ECS, so several tasks share one database,
and almost all of its work is waiting for that database.

## Decision

- **PostgreSQL** (RDS in AWS, `postgres:17` locally), not SQLite: several ECS
  tasks need one shared database, and the code relies on PostgreSQL features
  where they make it simpler and safe under concurrency: `INSERT … ON CONFLICT`
  for upserts, advisory locks for imports ([0004](0004-synchronous-csv-import.md)),
  array parameters and `CHECK` constraints.
- **Async all the way**: FastAPI endpoints, SQLAlchemy 2's `AsyncSession`,
  the asyncpg driver. One process per container; capacity is added by running
  more tasks, not workers.
- **A thin layering**: `api/` (HTTP, status codes, problem details) calls
  `services/` (queries and rules), which use `models.py`. Pydantic schemas in
  `schemas.py` are the API contract and the source of the OpenAPI document.
- Tests run against a real PostgreSQL, each test in a transaction that is
  rolled back, rather than against mocks or SQLite.

## Alternatives

- **Synchronous SQLAlchemy**, run in FastAPI's thread pool. Simpler to debug,
  but every request holds a thread while it waits for the database, and mixing
  `def` and `async def` endpoints is an easy way to block the event loop.
- **SQLite**: no server to run, but not shareable between ECS tasks.

## Consequences

- Lazy loading is unavailable in async code; relationships are loaded
  explicitly (`selectinload`), and a missing one fails loudly instead of
  issuing hidden queries.
- asyncpg allows at most 32,767 parameters per statement, so lookups of many
  values pass one array (`= ANY(:values)`) instead of a long `IN` list.
- Tests need Docker for the database; CI starts it the same way as a developer
  does (`docker compose up db`).
