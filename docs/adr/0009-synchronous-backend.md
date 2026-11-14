# 0009 — A synchronous backend

Status: accepted, supersedes the async part of [0001](0001-async-fastapi-postgres.md)

## Context

[0001](0001-async-fastapi-postgres.md) made the backend asynchronous. Looking
at what the application actually does, that bought nothing and cost something:

- It is a small internal tool: a few team leads at a time, each request one or
  two indexed queries of a few milliseconds. Async pays off with many
  concurrent connections or many outbound calls per request; there are neither.
- The heaviest work, parsing an uploaded CSV, is CPU-bound: 20,000 rows take
  about 1.2 seconds. Inside an `async def` endpoint it blocked the event loop,
  so every other request on the container, health checks included, waited for
  the parse to finish.
- Async had a price in the code: no lazy loading (a forgotten
  `selectinload` fails with `MissingGreenlet`), an event loop shared by the
  whole test run, and the rule that nothing blocking may ever run in an
  endpoint.

## Decision

- **Endpoints are plain `def` functions** using SQLAlchemy's `Session` and the
  **psycopg 3** driver. FastAPI runs them in its thread pool (40 threads by
  default), each request with its own session.
- Code that never touches the database stays on the ASGI level as it is:
  middleware, error handlers and the static file serving of
  [0003](0003-single-image.md).
- Connections time out after 5 seconds. libpq has no connect timeout of its
  own, so an unreachable database would otherwise hold a request, and its
  thread, until the operating system gives up after about two minutes.
- Tests call the application through FastAPI's `TestClient`; the transaction
  rolled back after each test is unchanged.
- Relationships stay loaded explicitly (`selectinload`), even though lazy
  loading would work now, so that lists do not issue a query per row.

The rest of [0001](0001-async-fastapi-postgres.md) still applies: PostgreSQL,
the layering, and testing against a real database.

## Alternatives

- **Keep async and move the parsing to a thread** (`asyncio.to_thread`): fixes
  the blocked event loop, but keeps the complexity for a concurrency this
  application does not have.

## Consequences

- A long request, such as a large import, occupies one thread and leaves the
  others free: during a 20,000-row import `/readyz` keeps answering in 10–120 ms.
- Concurrency per task is bounded by the thread pool and by SQLAlchemy's
  connection pool (5 connections plus 10 overflow); requests beyond that wait
  for a free connection. Each ECS task can hold up to 15 database connections,
  which has to fit RDS's connection limit when scaling out.
- Should the application one day hold many open connections or call other
  services within requests, async is worth revisiting.
