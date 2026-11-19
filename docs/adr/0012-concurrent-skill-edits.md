# 0012 — Saving skills only over the version they were edited from

Status: accepted

## Context

An employee's skills are saved as a whole: the panel collects edits in a draft
and `PUT /employees/{id}/skills` replaces the employee's set with it. Two team
leads with the same employee open would overwrite each other unseen: A adds Go
and saves, B, still showing the skills from before, adds Rust and saves, and
Go is gone. Nothing tells either of them.

## Decision

- **Optimistic concurrency with HTTP's own headers.** `GET /employees/{id}`
  returns the employee's version as an `ETag`; `PUT …/skills` takes it in
  `If-Match` and is refused with `412 Precondition Failed` when the employee
  has changed since, and with `428 Precondition Required` without it, so that
  no client can overwrite unseen by forgetting the header. The response carries
  the new version, for the next save.
- **The version is a hash of the employee as the API shows it**, not a stored
  counter: whatever changes what the API shows changes it — a skill, a level,
  an import updating the job title, a renamed skill — with no column to keep
  up to date and no migration. The skills are always shown in the same order,
  so the same employee always has the same version.
- **The check and the write are one transaction, with the employee's row
  locked** (`SELECT … FOR UPDATE OF employee`). Of two saves from the same
  version at the same moment, the second waits for the first, then finds the
  new version and is refused; without the lock both could pass the check.
- **The panel says what happened** and offers the latest version; the user
  redoes their changes on it rather than having the application merge them.

## Consequences

- Lost updates are impossible through the API, not just through the frontend.
- An unrelated change, say an import changing the job title, also refuses a
  save of skills from before it. That is rare and costs one reload.
- Any other client has to read the employee before changing its skills, which
  a client replacing the whole set should do anyway.

## Alternatives considered

- **A version column** incremented on every change: the classic, but every
  write path — the skills, the import, a renamed skill shown on many employees —
  would have to remember to increment it.
- **Last write wins**: what there was; simple, and silently loses data.
- **Per-skill endpoints** (`PUT/DELETE /employees/{id}/skills/{skill_id}`),
  which only touch one assignment and so conflict less: they existed, but the
  frontend never used them, and a draft saved as several requests could half
  succeed. They were removed.
