# Security policy

## Supported scope

Security fixes target the current `main` branch. This repository does not
provide a response-time SLA.

## Reporting a vulnerability

Do not publish exploit details in a GitHub issue. Contact the maintainer
privately with the affected revision, impact, reproduction steps, and a minimal
proof of concept where possible.

## Security model

Abundance assumes that inquiries, retrieved pages, model output, headers, and
browser storage are untrusted.

- Search adapters are read-only and invoked only for code-authorized units.
- Retrieved URLs pass an HTTP(S)-only admission and deduplication policy.
- Claims and rendered citations are bound to admitted evidence IDs.
- Raw model HTML is never injected into the DOM.
- Provider errors are mapped to public codes and correlation IDs.
- Browser requests use encrypted HTTP-only cookies, SameSite Strict, origin
  checks, body limits, and distributed production rate limits.
- The internal research endpoint can require a separate bearer token.

## Secret handling

- Never commit `.env` files, provider keys, session secrets, passwords, Redis
  tokens, or internal service tokens.
- Use at least 32 random bytes for `SESSION_SECRET` and the service token.
- Rotate a secret immediately if it appears in history, logs, screenshots, or a
  remote branch. Deleting the current file is not sufficient.
- Store production secrets in the deployment platform's secret manager.
- Keep `RESEARCH_BACKEND_TOKEN` and `ABUNDANCE_INTERNAL_API_TOKEN` identical but
  scoped to their respective services.

## Production boundary

Before public exposure:

1. terminate TLS at a trusted proxy;
2. keep FastAPI on a private network or require its bearer token;
3. configure Upstash Redis for shared login and research limits;
4. restrict CORS to exact frontend origins;
5. apply provider-side quotas and budget alerts;
6. run both dependency audits and container builds;
7. configure a durable checkpointer before advertising resumable runs;
8. define retention and deletion policies for checkpoints and logs.

The password gate is suitable for a private single-user deployment. It is not a
replacement for multi-user identity, roles, audit trails, or account recovery.
