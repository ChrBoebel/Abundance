# Staging delivery runbook

Abundance stages immutable backend and frontend images through the manually approved `Staging Delivery` workflow. The `staging` GitHub environment exists, but deployment remains disabled until its host, URL, and secrets are configured.

## Required infrastructure

- One Linux host with Docker Engine, the Compose plugin, and an HTTPS reverse proxy.
- DNS and TLS for the value stored as the `STAGING_BASE_URL` environment variable.
- A non-root SSH account allowed to operate the remote Docker engine.
- A GHCR token restricted to reading this repository's packages.
- An Upstash database dedicated to staging.
- Separate staging credentials for OpenRouter and Tavily.

The reverse proxy must forward the public staging origin to `127.0.0.1:4290`. PostgreSQL and the research backend are intentionally not published on the host network.

## GitHub environment configuration

Configure these environment variables:

- `STAGING_BASE_URL`
- `STAGING_PORT` (normally `4290`)

Configure these encrypted environment secrets:

- `STAGING_HOST`, `STAGING_USER`, `STAGING_SSH_KEY`, `STAGING_KNOWN_HOSTS`
- `GHCR_READ_TOKEN`
- `POSTGRES_PASSWORD`, `INTERNAL_API_TOKEN`, `SESSION_SECRET`, `APP_PASSWORD`
- `RATE_LIMIT_KEY_SECRET`
- `OPENROUTER_API_KEY`, `TAVILY_API_KEY`
- `UPSTASH_REDIS_REST_URL`, `UPSTASH_REDIS_REST_TOKEN`

Generate independent random values for every environment. Do not reuse production or local development credentials.

## First deployment

1. Run `Staging Delivery` on a reviewed commit.
2. Keep `publish=true`, set an immutable `image_tag` such as `rc-2026-08-25-1`, and keep `deploy=false`.
3. Confirm both GHCR packages exist and their build provenance points at the intended commit.
4. Run the workflow again with `publish=false`, the same tag, and `deploy=true`.
5. Keep `run_research_smoke=false` for the infrastructure-only deployment.
6. After health checks pass, run once more with the same tag and `run_research_smoke=true` to exercise login, providers, streaming, and completion.

The migration container runs before the backend. The backend fails readiness if the application schema is absent. LangGraph's checkpoint migrations are applied by the same explicit migration command.

## Verification

- `/api/health` reports both frontend and backend healthy.
- The authenticated smoke stream contains `run.completed`.
- Structured backend logs include a request ID, run ID, duration, and no prompt or secret content.
- A completed run survives a container restart.
- A generated share URL works without exposing the internal API token.

## Rollback

1. Select the last known-good immutable image tag from GHCR.
2. Run `Staging Delivery` with `publish=false`, `deploy=true`, and that tag.
3. Leave the PostgreSQL volume in place. Application migrations are forward-only in staging and production.
4. If a schema correction is needed, ship a new forward migration; do not edit an applied SQL file.
5. Run the infrastructure and provider-backed smoke tests again.

The prior images remain addressable by both the chosen release tag and `sha-<commit>`. Never roll back by rebuilding an old mutable tag.

