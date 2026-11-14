# 0005 — Proficiency levels as ordered integers

Status: accepted

## Context

Each assigned skill has a proficiency level, and the central question of the
application is "who knows Kubernetes at an advanced level?". Someone looking
for an advanced Kubernetes engineer is just as happy with an expert, so levels
have an order, and a search for a level means that level or higher.

## Decision

- Four levels: beginner, intermediate, advanced, expert.
- **Stored as `SMALLINT` 1–4** with a `CHECK` constraint, mapped to a Python
  `IntEnum`. **The API speaks names** (`"advanced"`), never numbers.
- **A search criterion means "at least"**: `skill=kubernetes:advanced` is
  `level >= 3`, answered from the `(skill_id, level)` index. A skill without a
  level matches any level; several criteria must all match.
- A misspelt level is rejected with a 422 rather than matching nobody.

## Alternatives

- **Strings** (`'advanced'`): readable in the database, but they sort
  alphabetically, so "at least" becomes a list of values in every query.
- **A PostgreSQL `ENUM`**: ordered, but changing it needs `ALTER TYPE`, which is
  awkward in migrations.
- **A finer scale** (1–10): precision that self-assessments do not have.

## Consequences

- "At least" is one comparison and an index range scan.
- Adding a level between two existing ones means renumbering stored values in
  a migration; with four established levels, that is unlikely.
