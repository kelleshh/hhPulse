# Iteration 3 — complete frontend workspace

## Scope

This iteration changes the presentation and frontend integration layer only.
Domain, application, HH adapters, persistence and execution semantics remain
unchanged.

The new `frontend/` application covers the complete intended navigation:

- daily overview and data-quality tape;
- role comparison and experience-strata comparison;
- one-day market snapshot with HH facet distributions;
- analysis-job creation, enable/disable and manual run trigger;
- persisted daily-run progress;
- operational events;
- frontend preferences and CSV export.

## Data modes

`VITE_DATA_MODE=demo` is the default development mode. It is deterministic,
requires no backend and persists user actions to browser storage.

`VITE_DATA_MODE=api` connects existing job and run-progress routes directly to
FastAPI. Missing analytical read models are not faked in this mode: requests
fail visibly. Their exact frontend contract is documented in
`frontend/docs/api-contract.md` for the next backend-focused iteration.

## Frontend boundaries

The UI consumes data through one typed `DataRepository` interface. Demo and
HTTP implementations sit behind that boundary. API snake_case is mapped at the
HTTP edge and does not leak through React components. Server state is owned by
TanStack Query; view state remains local to the page that controls it.

## Visual system

The interface is an analytical workstation rather than a generic card
dashboard. Its characteristic element is the market tape: a thirty-day line of
published days, honest gaps, current progress and parser-contract failures.
Colour has semantic meaning, charts always expose a table equivalent, and the
layout adapts from a fixed desktop rail to mobile bottom navigation.

The complete design plan and self-critique are in `frontend/DESIGN.md`.

## Verification

- TypeScript strict production build;
- ESLint with zero warnings;
- seven Vitest tests;
- desktop visual QA at 1440×1000;
- mobile visual QA at 390×844;
- responsive layout, visible keyboard focus and reduced-motion support;
- Docker Compose syntax parsed successfully.

