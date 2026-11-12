# Staff & Skill Planning Tool

An internal tool for team leads: import employees from a CSV, keep track of
their skills and proficiency levels, and answer questions such as *"who knows
Kubernetes at an advanced level?"* without asking around in chat.

> **Status: milestone M1 — domain model.** The toolchain, quality gates, the
> database schema and its migrations are in place; the features are built in
> the milestones listed under [Roadmap](#roadmap). Each milestone is a
> self-contained commit with its own tests.

## Tech stack

| Layer    | Choice                                                                     |
| -------- | -------------------------------------------------------------------------- |
| Backend  | Python 3.12, FastAPI, SQLAlchemy 2.0 (async), PostgreSQL, Alembic           |
| Frontend | TypeScript, Angular 22 (standalone, signals, zoneless), Siemens Element     |
| Tooling  | uv, ruff, mypy, pytest · npm, ESLint, Prettier, vitest · Docker, Compose    |

## Repository layout

```
.
├── backend/          FastAPI application (uv project)
│   ├── app/          application code
│   └── migrations/   Alembic migrations
├── frontend/         Angular application (npm project)
├── docker/postgres/  database init script (creates the test database)
└── docker-compose.yml
```

One repository rather than two: the backend contract and the frontend that
consumes it change together, and at this size a split would only add
coordination overhead. The two applications stay independently buildable and
are shipped as separate container images.

## Prerequisites

- [uv](https://docs.astral.sh/uv/) (Python toolchain and dependency manager)
- Node.js 22+ and npm 11+
- Docker (for PostgreSQL)

## Quick start

### Database

```bash
docker compose up -d --wait db   # PostgreSQL 17 on localhost:5432
```

This creates two databases: `skills` for the application and `skills_test`
for the test suite, which migrates it from scratch on every run.

### Backend

```bash
cd backend
uv sync                               # create .venv from uv.lock
uv run alembic upgrade head           # apply migrations
uv run uvicorn app.main:app --reload  # http://localhost:8000/docs
```

New migration after a model change:
`uv run alembic revision --autogenerate -m "<what changed>"`, then review the
generated file before applying it.

Configuration comes from the environment; every variable is prefixed with
`APP_` and documented in `backend/app/core/config.py`. Create `backend/.env`
for local overrides, for example:

```dotenv
APP_ENVIRONMENT=local
```

### Frontend

```bash
cd frontend
npm ci                  # install from package-lock.json
npm start               # http://localhost:4200
```

## Quality gates

The same commands run locally and in CI, so a green local run means a green
pipeline.

| Check            | Backend                 | Frontend              |
| ---------------- | ----------------------- | --------------------- |
| Lint             | `uv run ruff check .`   | `npm run lint`        |
| Format           | `uv run ruff format .`  | `npm run format`      |
| Types            | `uv run mypy`           | part of `npm run build` |
| Tests + coverage | `uv run pytest`         | `npm run test:ci`     |

Both suites fail below 80% coverage. The backend tests need the database
from `docker compose up -d db`.

## Roadmap

| Milestone | Scope                                                               |
| --------- | ------------------------------------------------------------------- |
| M0        | Scaffolding, tooling and quality gates                              |
| M1        | Domain model, PostgreSQL, Alembic migrations                        |
| M2        | Employee read API (pagination, sorting, filtering)                  |
| M3        | CSV import: parsing, validation, idempotent upsert, import report   |
| M4        | Skill catalogue and skill assignment                                |
| M5        | Skill search with "at least this level" semantics                   |
| M6–M9     | Frontend: shell, employee overview, import, skill assignment, search |
| M10       | Container images and Docker Compose                                 |
| M11       | CI/CD pipeline, architecture decision records, documentation        |

The M0 landing page is a placeholder that doubles as a check on the design
system setup: `frontend/src/app/button-showcase/` is the button example from the
Siemens Element documentation, included verbatim (MIT) to confirm that the
theme, the icon font and the CDK overlay styles are wired correctly. It is
removed once the real views arrive in M6.

## Non-goals

Deliberately out of scope, and why:

- **Authentication and authorisation.** In the target environment this is
  handled in front of the application (OIDC at the load balancer); the
  application only needs an injection point for the current user. Building a
  login of our own would demonstrate the wrong thing.
- **Audit logging and soft deletes.** Valuable in a real HR-adjacent system,
  but they would dominate the code without adding to what this case study is
  about.
- **Internationalisation.** The UI is English-only.
