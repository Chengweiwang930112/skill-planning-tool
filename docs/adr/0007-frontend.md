# 0007 — Element, generated API types and state in the URL

Status: accepted

## Context

The frontend is an Angular application for team leads inside Siemens. It
should look and behave like the other internal tools, and stay correct while
the API evolves.

## Decision

- **Siemens Element** for components and styling (application header, side
  panel, typeahead, file drop zone, pagination, badges), instead of building
  them or using another library.
- **Current Angular**: standalone components, zoneless change detection,
  signals, and `httpResource` for reading data. Writes go through `HttpClient`.
- **API types are generated** from the backend's OpenAPI document
  (`npm run api:types`) and committed. An API change that breaks the frontend
  fails the build, and CI fails when the generated types are out of date.
- **Page state lives in the URL**: search text, sorting, page, skill criteria
  and the employee open in the side panel. Views can be bookmarked and shared,
  and the back button works.
- **Edits are drafts saved in one request.** The employee panel collects skill
  changes and **Save** replaces the employee's skills with one
  `PUT /employees/{id}/skills`, applied completely or not at all.
- Errors are shown from the API's problem details (RFC 9457), so the backend
  owns the wording.

## Alternatives

- **Angular Material or a custom design**: would not match Siemens tools.
- **Hand-written API interfaces**: drift silently from the backend.
- **A state management library**: signals and the URL already hold all state
  this application has.

## Consequences

- The frontend depends on Element's release cycle and its Angular support.
- The generated types have to be regenerated after API changes; CI enforces it.
