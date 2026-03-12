# Security Policy

## Supported Scope

This repository is maintained as a portfolio project and demo application. Security fixes may be applied on a best-effort basis, but no formal SLA is provided.

## Reporting A Vulnerability

If you discover a security issue, do not open a public GitHub issue with exploit details.

Instead:

1. Contact the maintainer privately.
2. Include a clear description of the issue, impact, and reproduction steps.
3. If possible, include a minimal proof of concept and affected files.

## Secret Handling

- Never commit `.env` files or real API keys.
- Rotate any provider keys immediately if they were exposed in local history, screenshots, logs, or remote branches.
- Use the placeholder values in `backend/.env.example` and `frontend/.env.example` as the only committed configuration examples.

## Deployment Notes

- The frontend auth layer is intentionally lightweight and designed for private demos, not high-security production environments.
- Before any public deployment, review CORS, session configuration, secret storage, and provider quotas.
