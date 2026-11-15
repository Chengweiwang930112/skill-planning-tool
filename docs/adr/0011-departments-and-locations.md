# 0011 — Departments and locations as records of their own

Status: accepted

## Context

Department and location arrive as free text in each imported CSV row and were
stored that way on the employee. Team leads want to filter the employee list by
them, choosing from the ones that exist rather than typing a name that may match
nothing. Free text also lets one department exist in several spellings —
`Mobility`, `mobility`, `Mobility ` — the problem the skill catalogue solved for
skills ([0006](0006-skill-catalogue.md)).

## Decision

- **Departments and locations are tables** (`department`, `location`: `id`,
  `name`, unique `key`), and an employee refers to one of each.
- **Imports maintain them.** A department or location new to the database is
  added (`INSERT … ON CONFLICT DO NOTHING` on the key), in the first spelling
  seen; there is no page to manage them.
- **The same key as skills**: case, spaces and punctuation do not count. A name
  without a letter or digit, such as `-`, means none.
- **Filters by name, matched by key**:
  `?department=Mobility&department=Healthineers&location=Munich` — any of the
  departments, and any of the locations — so that a filtered view is a readable,
  shareable URL, as the skill criteria are.
- The migration merges the existing spellings of a department under the one
  most employees have, and a downgrade writes the names back.
- The API still shows an employee's department and location as names.

## Alternatives

- **Keep the text and offer its distinct values**: no migration, but the
  spellings stay separate in the list and in the filter.
- **Filter by id**: unambiguous, but the URL means nothing to a reader.

## Consequences

- The filter offers exactly what employees have, and a different spelling in
  a later import lands in the same department.
- A misspelt department in a file still becomes a department of its own. As
  departments are not edited in the app, fixing one means a corrected import or
  a database change; a management page like the skill catalogue's is the next
  step if that becomes common.
