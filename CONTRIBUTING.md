# Contributing to Abundance

## Workflow

1. Create a focused branch from `main`.
2. Keep domain decisions separate from graph, transport, and provider details.
3. Add a regression test for every behavior change or repaired defect.
4. Run the full local gates documented in the root README.
5. Use a descriptive Conventional Commit message.
6. Open a pull request; do not rewrite shared branch history.

Examples:

- `feat(evidence): assess publication freshness`
- `fix(workflow): cancel queued evidence units`
- `test(stream): preserve split SSE frames`

## Architecture rules

- Domain models must not import FastAPI, LangGraph, LangChain, or provider SDKs.
- LangGraph state must remain checkpoint-serializable.
- Public clients consume Abundance events, not runtime callback events.
- Models do not receive write-capable tools.
- Search budgets and URL admission are code controls, not prompt instructions.
- Reports may cite only evidence admitted by the application policy.
- Provider exceptions stay server-side.

## Research principles

Changes to research behavior should connect material claims to evidence, seek
credible counterevidence, distinguish observation from inference, expose
uncertainty, prefer primary sources where appropriate, and never describe
retrieval alone as verification.

## Pull-request checklist

- [ ] Tests cover the changed contract or repaired regression.
- [ ] Ruff, mypy, pytest, ESLint, TypeScript, Vitest, and builds pass as relevant.
- [ ] Dependency audits report no known vulnerabilities.
- [ ] Documentation and environment examples match runtime behavior.
- [ ] No secrets, generated builds, or local environment files are staged.
- [ ] Third-party licenses and notices remain intact.

## Attribution

Do not remove third-party copyright, repository history, or license notices.
When adapting additional open-source code, update `THIRD_PARTY_NOTICES.md` in
the same change.
