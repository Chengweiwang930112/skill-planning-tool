# 0003 — One container image, the API serving the frontend

Status: accepted

## Context

The application has two parts, the FastAPI backend and the Angular frontend,
which after the build is a folder of static files. Both are deployed to ECS.
The frontend is generated from the backend's API, so the two only work in
matching versions.

## Decision

One image (the root `Dockerfile`, three stages: Node build, `uv sync`, slim
Python runtime) contains the API and the built frontend. FastAPI serves:

- `/api/v1/…`, `/docs`, `/healthz`, `/readyz` — the API;
- every other path from the frontend build, falling back to `index.html` so
  that deep links such as `/employees?employee=12` work (`core/frontend.py`).
  Unknown `/api/…` paths stay a JSON 404 and never get the HTML page.

Built files with a content hash in their name are cached for a year
(`immutable`); `index.html` and everything else is revalidated (`no-cache`),
so a deployment takes effect at the next page load. Responses are gzipped.

## Alternatives

- **Two images**, nginx for the frontend and one for the API: two things to
  build, version, deploy and scale in step, and either CORS or a proxy between
  them.
- **Frontend on S3 and CloudFront**: the better choice for a public site with
  users far away; for an internal tool it adds a second deployment target and
  an invalidation step without a noticeable gain.

## Consequences

- One artefact, one version: frontend and API can never be deployed out of
  step, and the pair is tested together (the CI smoke test).
- Same origin, so no CORS configuration.
- Python serves static files. That is cheap here, because browsers cache the
  hashed files; should it ever matter, a CDN can be put in front without code
  changes, since the API stays under its own prefix.
