# Code Style Rules

- Python 3.10+ — use modern syntax: `list[str]` not `List[str]`, `X | None` not `Optional[X]`
- Use Pydantic v2 models for all data structures that cross module boundaries
- Use dataclasses for internal/transient structures
- Type hints on all function signatures — no untyped public functions
- Line length: 100 characters (configured in pyproject.toml ruff settings)
- Import sorting: isort-compatible (stdlib, third-party, local) — ruff handles this
- All scoring functions must return `float` in range `[0.0, 1.0]`
- All database operations go through the `db/` module — never raw SQL in other layers
- Use `pathlib.Path` for file paths, not raw strings
- Logging via `logging` module, not `print()` — except in CLI output
- Use `uuid4()` for all entity IDs
