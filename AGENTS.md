# Development guidelines

## Project direction

- Keep the project flexible, lightweight, and extensible. Do not add frameworks or abstraction layers for hypothetical needs.
- Keep domain calculations independent from HTTP, files, presentation, and generated reports.
- Prefer explicit data models and small composable functions over global state.
- Treat upstream contest data as untrusted input and report validation failures with useful context. Where real upstream data contains known ambiguity, use a documented deterministic policy and offer strict validation when practical.

## Tests

- New features and bug fixes require focused unit tests.
- Pure rating and selection rules must have deterministic regression tests.
- Default tests must not require network access. Use injected HTTP transports and committed, reduced fixtures.
- Keep a small end-to-end test across data adaptation, season ordering, and rating calculation.

## Design documents

- Each feature belongs to a design document under `doc/`; `doc/README.md` maps features to documents.
- Before changing an existing feature, read its relevant design document.
- Before considering work complete, return to that document and update its behavior, public API, data assumptions, known limitations, and test coverage.
- If implementation and documentation disagree, update both in the same change or explicitly document the design decision. Do not leave them knowingly inconsistent.
- Public API changes also require updates to `README.md` and the relevant `src/core/__init__.py` or `src/rating/__init__.py` exports.
