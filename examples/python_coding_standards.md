# Python Coding Standards and Architecture Decisions

**Source:** Internal Engineering Standards
**Version:** 1.0

## Code Style

### Formatting

- Max line length: 120 characters
- Double quotes for user-facing strings, log messages, and docstrings
- Single quotes for internal strings: dict keys, identifiers, config values
- No blank lines between import groups - keep imports compact
- Import order: stdlib, third-party, local (relative imports within package)

### Naming Conventions

- Classes: PascalCase (`UserService`, `OrderRepository`)
- Functions and variables: snake_case (`get_user`, `order_total`)
- Constants: UPPER_SNAKE_CASE (`MAX_RETRIES`, `DEFAULT_TIMEOUT`)
- Private members: single underscore prefix (`_validate`, `_cache`)
- Avoid abbreviations except well-known ones (`url`, `id`, `db`)

### Type Hints

- Annotate all public function signatures
- Use modern union syntax: `str | None` instead of `Optional[str]`
- Use `list[str]` instead of `List[str]`, `dict[str, int]` instead of `Dict`
- Use `TypedDict` for structured dicts passed between functions
- Use `str = None` for optional parameters with None default, not `str | None = None`

## Project Structure

### Layout

- Use src/ layout: `src/myapp/__init__.py`
- Separate concerns into modules: `models/`, `services/`, `api/`, `utils/`
- Keep CLI entry points thin - delegate logic to service layer
- One module per domain concept, avoid catch-all `utils.py` files

### Dependencies

- Pin versions in `requirements.txt` for production deployments
- Use `pyproject.toml` for package metadata and dev dependencies
- Virtual environments are mandatory - never install globally
- Prefer stdlib over third-party for simple tasks

## Implementation Guidelines

### Functions and Methods

- Max function length: 30 lines - extract helpers if longer
- Max arguments: 5 - use dataclasses or TypedDict for more
- Single responsibility - one function does one thing
- Prefer returning values over mutating arguments
- Use keyword arguments for boolean flags: `save(overwrite=True)`

### Classes

- Prefer composition over inheritance
- Use dataclasses for data containers, avoid `__init__` boilerplate
- Use `@cached_property` for expensive computed attributes
- Keep `__init__` simple - no complex logic, no I/O

### Error Handling

- Validate at system boundaries only (user input, external APIs)
- Chain exceptions with `from` to preserve context: `raise ValueError(...) from e`
- Suppress noisy chained tracebacks when re-raising: `raise Error(...) from None`
- Use specific exception types, never bare `except:`
- Log errors with `%s` placeholders, not f-strings: `logger.error("Failed: %s", e)`

### Logging

- Use stdlib `logging` module, never bare `print()` for operational output
- Always use `%s`-style placeholders: `logger.info("Processing %s items", count)`
- Use `logger = logging.getLogger(__name__)` at module level
- Log at appropriate levels: DEBUG for internals, INFO for milestones, ERROR for failures

## Testing

### Framework and Structure

- Framework: pytest
- Group tests in classes: `class TestUserService:`
- Test file naming: `test_<module>.py`
- Assertions use plain `assert`, not `assertEqual`

### Patterns

- Use `unittest.mock` for external dependencies (APIs, DB, filesystem)
- Use `pytest.mark.parametrize` for data-driven tests
- Test `_build_inputs`, `_update_state`, and schema validation directly rather than full async flows
- Tests are synchronous wherever possible

## Architecture Decisions

### Async Strategy

- Async/await for I/O-bound operations (HTTP, DB, filesystem)
- Synchronous code for CPU-bound and simple scripts
- Use `asyncio.wait_for()` for timeouts on async calls

### Data and Storage

- Use Pydantic for data validation at API boundaries
- SQLite for local storage, PostgreSQL for production
- Configuration via environment variables, never hardcoded
- Secrets must never appear in source code or logs
