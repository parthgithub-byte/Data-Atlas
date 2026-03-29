# Agile + CI/CD + DevOps Working Agreement

## Delivery Model

- Use short-lived branches from `develop` or `main`.
- Keep stories small enough to complete, review, and verify within one sprint.
- Every change should map to a ticket, user value, and acceptance criteria.

## Definition Of Ready

- Problem statement is clear.
- Acceptance criteria are testable.
- Security and data-privacy impact are considered.
- Rollback risk is understood.

## Definition Of Done

- Code is implemented and reviewed.
- Backend tests pass.
- Frontend syntax validation passes.
- CI passes before merge.
- Docs and environment notes are updated when behavior changes.

## CI Gates

- Python compilation succeeds.
- `unittest` suite passes.
- Frontend JavaScript syntax checks pass.
- Docker image builds successfully.
- `docker compose config` remains valid.

## CD Baseline

- GitHub Actions builds and publishes a container image to GHCR on `main` and version tags.
- Runtime secrets stay in environment variables or platform secret stores, never in source control.
- Compose deployments use persisted volumes for database and evidence data.
- Rotate app secrets with `python scripts/generate-secrets.py` when promoting environments or after any suspected exposure.

## Environments

- Local: `docker compose up --build`
- CI: GitHub Actions validation pipeline
- Release: image published to GHCR, then deployed by environment-specific automation

## Operational Guardrails

- Run containers as a non-root user.
- Health checks are required for core services.
- Shared services must use persistent volumes.
- Authentication, privacy, and ownership checks are part of every release review.
- Staging and production must use secure cookie settings and unique secrets per environment.
