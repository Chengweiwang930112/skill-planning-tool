# 0010 — Unit, component and integration tests

Status: accepted

## Context

Most backend tests used to go through the whole stack: an HTTP request, the
router, the service and a real database. Such a test exercises a lot of code at
once, so the coverage figure looked high while many branches were only passed
through on the way, not checked. A failure also pointed at the whole chain
rather than at the part that broke.

## Decision

The backend's tests live in three folders, by what they put together:

- **`tests/unit`** — functions on their own, no HTTP and no database: CSV
  parsing, the validation of requests (levels, `name:level` criteria, duplicate
  skills, names), skill keys, problem details, caching rules.
- **`tests/component`** — one module with what it talks to replaced by mocks:
  - the routers through FastAPI's `TestClient`, with the services replaced by
    `create_autospec` mocks: how requests reach the services, the shape of the
    responses, how errors map to status codes, and that invalid requests never
    reach a service;
  - the services with a mocked session: their control flow (what is committed,
    rolled back or refused before anything changes) and the SQL they send,
    rendered in PostgreSQL's dialect — that a skill criterion matches the
    catalogue key at `level >= n`, that inserts use `ON CONFLICT`, that lookups
    pass one array parameter.

  Autospec mocks fail when a call does not match the real function's
  signature, so mocks cannot drift from the code they replace.
- **`tests/integration`** — the real thing, and the only layer that needs the
  database container: requests through the HTTP API into PostgreSQL, the
  schema's constraints, the migrations, and one request through an
  application without any test overrides.

Every test is written as Given / When / Then, each part marked with a comment
(`# When / Then` where the action is the assertion, as with `pytest.raises`).
The frontend's specs follow the same structure; they stay next to the code
they test, as Angular expects.

## Alternatives

- **Markers instead of folders** (`@pytest.mark.unit`): every test has to
  carry one, and a forgotten marker goes unnoticed; a folder cannot be
  forgotten.
- **Component tests against SQLite** instead of a mocked session: faster than
  PostgreSQL, but the queries rely on PostgreSQL (`ON CONFLICT`, arrays,
  advisory locks), so SQLite would test a different database.

## Consequences

- In CI each layer is a job of its own, and the coverage that counts for the
  80% threshold and for SonarQube is that of unit and component tests
  combined ([0008](0008-ci-cd.md)): integration tests run too much code at once
  for their coverage to mean much.
- Unit and component tests run without Docker, in a few seconds. Each layer
  can run on its own (`uv run pytest tests/component`); measured alone, unit
  tests cover 44% of the code, component tests 95% and integration tests 93%,
  all of them together 100%.
- A component test can check that the SQL is what was meant, not that
  PostgreSQL answers it as expected; that is what the integration tests are
  for, so most rules are tested once with mocks and once for real.
- Component tests mirror the services' signatures and statements; changing
  either means updating them, which autospec enforces for the signatures.
