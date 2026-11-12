# Staff & Skill Planning Tool

An internal tool for team leads: import employees from a CSV, keep track of
their skills and proficiency levels, and answer questions such as *"who knows
Kubernetes at an advanced level?"* without asking around in chat.

> **Status: milestone M3 — CSV import.** The toolchain, quality gates, the
> database schema, the employee read API and the CSV import are in place; the features are built in
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
├── samples/          CSV files to try the import with
├── scripts/          dev.ps1 / dev.sh behind the Makefile
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

### Everything at once

```bash
make start     # database, migrations, then backend and frontend in the background
make stop      # stop backend, frontend and the containers (data is kept)
make restart
make clean     # stop, then delete containers, volumes (database data) and logs
```

The targets work the same from cmd, PowerShell and bash. They call
`scripts/dev.ps1` on Windows and `scripts/dev.sh` on Linux and macOS, which can
also be run directly, e.g. `powershell -File scripts\dev.ps1 start`.

Logs go to `.run/backend.log` and `.run/frontend.log`. The servers are stopped
by the port they listen on (8000, 4200), so `make stop` also cleans up servers
started by hand. The steps below do the same thing one at a time.

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
uv run python -m scripts.seed         # optional: fictional demo data (empty database only)
uv run uvicorn app.main:app --reload  # http://localhost:8000/docs
```

The API is documented with OpenAPI. Swagger UI at `/docs` lists every endpoint
with its parameters, response schemas and error responses, and **Try it out**
sends real requests. Errors use [RFC 9457](https://www.rfc-editor.org/rfc/rfc9457)
problem details (`application/problem+json`).

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

## Importing employees

`POST /api/v1/imports` takes a CSV file with a header row:

| Column            | Required | Notes                                         |
| ----------------- | -------- | --------------------------------------------- |
| `employee_number` | yes      | identifies the employee across imports        |
| `first_name`      | yes      |                                               |
| `last_name`       | yes      |                                               |
| `email`           | yes      | unique, stored in lower case                  |
| `department`      | no       |                                               |
| `job_title`       | no       |                                               |
| `location`        | no       |                                               |
| `hire_date`       | no       | `YYYY-MM-DD` or `DD.MM.YYYY`                  |

Column names are matched ignoring case and spaces (`Employee Number` works).
Files may be comma, semicolon or tab separated and UTF-8 or Windows-1252
encoded, which covers what Excel exports in German and English locales.

- **Importing again is safe.** Rows are matched by `employee_number`: new ones
  are created, changed ones updated, identical ones counted as unchanged.
- **Valid rows are imported even when others fail.** Each failed row is
  reported with its line number, column and reason: missing or invalid values,
  a duplicate employee number or email within the file, or an email that
  belongs to another employee.
- **Every upload is recorded** in `employee_import` with its status, the number
  of succeeded and failed rows, the row errors and the file's SHA-256, including
  files rejected as a whole (missing columns, no data rows, unreadable
  encoding). `GET /api/v1/imports` lists them.
- Imports run one at a time (a Postgres advisory lock), files are limited to
  5 MB and 10,000 rows.

The files in `samples/` cover these cases:

| File                         | Shows                                                        |
| ---------------------------- | ------------------------------------------------------------ |
| `employees.csv`              | a clean file; against the demo data: 2 created, 2 updated, 8 unchanged |
| `employees-excel-de.csv`     | a German Excel export: Windows-1252, `;`, CRLF, `DD.MM.YYYY` |
| `employees-with-errors.csv`  | one example of each row error next to valid rows             |

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
