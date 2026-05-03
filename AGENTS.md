# AGENTS.md — guidance for AI contributors

## Environment

This project uses **uv** for all Python tooling. Never call `python`, `pip`, or `pytest` bare.

```bash
uv sync --all-extras        # install / refresh all dev dependencies
uv run pytest               # run tests
uv run make check           # full local quality gate
uv run make help            # list all available targets
```

If a command fails with "module not found" or "command not found", run `uv sync --all-extras` first.

## Running checks

```bash
uv run make lint            # ruff + pylint (main code + tests)
uv run make typecheck       # mypy strict
uv run make test            # pytest with coverage
uv run make security        # bandit + uv audit + pip-audit
uv run make check           # everything above together
```

## Python conventions

- **`_` means unused, not private.** A leading underscore on a name signals "I'm not using this
  value" — it does not mean the name is private or internal. Use `__dunder__` for truly special
  methods and explicit `__all__` in modules that have a public API.
- All new code must have type annotations. The `python-use-type-annotations` pre-commit hook
  enforces this.
- Docstrings follow **Google style** (pydoctest and interrogate are configured for it).
- Line length is 120 characters (black + ruff configured to match).

## Tests

- Test files live in `tests/` (plural).
- Test functions are plain `def test_*` — no class required unless grouping is genuinely useful.
- Prefer `pytest` fixtures over `setUp`/`tearDown`.
- `hypothesis` is available for property-based tests.

## Dead code analysis

`vulture` and `deadcode` are available as **advisory** tools, not quality gates. Python's dynamic
nature means false positives are common. Use `__all__` in each module to declare the public surface
explicitly — that is the most reliable signal.

```bash
uv run make dead-code       # runs both vulture and deadcode (advisory only, non-blocking)
```

## Commits

Prefer a single clean commit per logical change on the main branch.
