# Architecture decision records

Each record explains one decision that shapes the code: the situation, what was
decided, the alternatives that were turned down, and what the decision costs.
Records are not edited once accepted; a changed decision gets a new record that
supersedes the old one.

| No.                                     | Decision                                                  |
| --------------------------------------- | --------------------------------------------------------- |
| [0001](0001-async-fastapi-postgres.md)  | Async FastAPI with SQLAlchemy 2 and PostgreSQL            |
| [0002](0002-reviewed-migrations.md)     | Reviewed migrations that run before the rollout           |
| [0003](0003-single-image.md)            | One container image, the API serving the frontend         |
| [0004](0004-synchronous-csv-import.md)  | A synchronous, repeatable CSV import                      |
| [0005](0005-ordered-levels.md)          | Proficiency levels as ordered integers                    |
| [0006](0006-skill-catalogue.md)         | A managed skill catalogue with a normalised key           |
| [0007](0007-frontend.md)                | Element, generated API types and state in the URL         |
| [0008](0008-ci-cd.md)                   | A GitHub Actions pipeline from lint to ECS                |
| [0009](0009-synchronous-backend.md)     | A synchronous backend (supersedes part of 0001)           |
