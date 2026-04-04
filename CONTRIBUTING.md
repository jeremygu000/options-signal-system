# Contributing to Options Signal System

Thanks for your interest in contributing! This guide will help you get started.

## Development Setup

### Prerequisites

- Python 3.12+
- Node.js 20+
- [uv](https://docs.astral.sh/uv/) (Python package manager)

### Backend

```bash
uv sync
uv run uvicorn app.server:app --reload --port 8400
```

### Frontend

```bash
cd web
npm install
npm run dev
```

## Code Quality

Run **all checks** before submitting a PR:

### Backend

```bash
uv run pytest              # 139+ tests
uv run mypy app/           # strict mode, zero errors expected
uv run black app/ tests/   # formatter
```

### Frontend

```bash
cd web
npm run typecheck           # tsgo --noEmit
npm run lint                # oxlint, zero warnings expected
npx prettier --check .      # formatter
npm run build               # production build
```

## Pull Request Process

1. Fork the repo and create a feature branch from `main`.
2. Make your changes — keep PRs focused on a single concern.
3. Ensure all checks listed above pass locally.
4. Write or update tests for any new functionality.
5. Open a PR with a clear title and description.

## Commit Convention

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(greeks): add rho calculation to BS engine
fix(server): handle empty options chain gracefully
docs: update API endpoint reference
test(iv): add IV rank edge-case tests
chore: update dependencies
```

## Architecture Overview

```
app/               Python backend (FastAPI)
├── server.py      API endpoints
├── greeks.py      Black-Scholes Greeks engine
├── iv_analysis.py IV analysis (rank, skew, term structure)
├── models.py      Pydantic models
├── config.py      Settings (pydantic-settings)
└── ...

web/               Next.js frontend
├── src/app/       App Router pages
├── src/lib/       API client, types
└── src/components/ Shared components

tests/             pytest test suite
```

## Docker

```bash
docker compose up --build
```

This starts both the backend (port 8400) and frontend (port 3100).

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
