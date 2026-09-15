# Repository Working Agreement

## Scope and architecture

- Build a Python 3.11+ modular monolith under `src/ops_agent`.
- Keep Knowledge, Reasoning, Investigation, and Reproduction as independent packages.
- Engines must not import another engine's implementation.
- Core Runtime is the only workflow orchestrator and calls engines through ports.
- FastAPI belongs only in external API adapters.
- LangChain belongs only in adapter or integration boundaries.
- Contracts, core, and domain code must not import FastAPI or LangChain.
- Public cross-module data must use Pydantic v2 models.
- Every port and integration must support deterministic fake implementations.

## Development workflow

1. Read the architecture plan and inspect the working tree before changing files.
2. Write or update a failing test before implementation.
3. Implement the smallest scoped change.
4. Run the focused test and fix failures.
5. Run `ruff check .`, `ruff format --check .`, `mypy`, and `pytest`.
6. Report the exact commands, results, unverified items, and residual risks.

Preserve unrelated changes and do not advance to a later architecture step unless requested.

