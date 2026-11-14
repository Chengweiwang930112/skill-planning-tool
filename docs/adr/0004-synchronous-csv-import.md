# 0004 — A synchronous, repeatable CSV import

Status: accepted

## Context

Team leads keep their people in Excel sheets and will upload exports of them,
again and again, with the usual flaws: German and English Excel formats,
missing values, duplicates. One upload holds a team or a department, up to a
few tens of thousands of rows.

## Decision

- **The upload is processed within the request** and answered with the import
  report. Limits keep that within an HTTP request: 10 MB and 50,000 rows;
  20,000 rows take about four seconds.
- **Importing is repeatable.** Rows are matched by `employee_number` and upserted
  (`INSERT … ON CONFLICT DO UPDATE`): new employees are created, changed ones
  updated, identical ones counted as unchanged. Importing the same file twice
  changes nothing.
- **Valid rows are imported even when others fail**, and each failed row is
  reported with its line, column and reason. A file that cannot be read at all
  (wrong columns, no rows, unknown encoding) fails as a whole.
- **Every upload is recorded** (`employee_import`): status, counts, row errors
  and the file's SHA-256, including uploads that failed.
- **Imports run one at a time**, serialised by a PostgreSQL advisory lock held
  for the transaction, so two uploads cannot race on the same new employee.
- **The parser is lenient about format, strict about content**: comma,
  semicolon or tab; UTF-8 or Windows-1252; header names ignoring case and
  spaces; but every value is validated.

## Alternatives

- **A background job** (SQS and a worker, or a task table): needed once
  imports take minutes, but it brings a queue, a worker service and polling to
  the UI. The import record already has a status, so the move stays open.
- **All or nothing**: one bad row out of thousands would block everyone else's
  data, and the lead would have to fix the file before seeing anything.

## Consequences

- An upload occupies one request for its duration; larger files need the
  background job above, not higher limits.
- Employees missing from a later file are kept, not deleted: an export of one
  team must not remove the others.
