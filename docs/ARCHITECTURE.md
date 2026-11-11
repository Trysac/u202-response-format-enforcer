# Architecture

## Purpose

`response_format_enforcer` validates LLM replies as CSV with typed columns, read-only SQLite `SELECT` statements, or a full-match regex, and provides a bounded re-ask loop.

## Shape

```text
caller code --> response_format_enforcer (public API in src/response_format_enforcer/__init__.py)
                    |
                    +-- CsvFormat / SqlFormat / RegexFormat
                    +-- validate / enforce
                    +-- Issue / FormatError
                    +-- Message / LLMPort / RecordedLLM / FakeLLM / RecordingExhaustedError
```

- **Public API**: the names listed in `__all__` of `src/response_format_enforcer/__init__.py`. Anything else is internal.
- **CSV**: `CsvFormat` is a frozen dataclass with `columns`, `types` and `max_rows`; validation uses the standard `csv` module and returns `Issue` objects.
- **SQL**: `SqlFormat` opens a private `sqlite3` `:memory:` connection, executes the schema DDL at construction, installs an authorizer that allows only `SQLITE_SELECT`, `SQLITE_READ` and `SQLITE_FUNCTION`, and validates statements with `EXPLAIN` without executing them.
- **Regex**: `RegexFormat` compiles the pattern at construction and validates with `re.fullmatch`.
- **Re-ask loop**: `enforce()` validates each reply, appends assistant and user feedback messages on failure, and raises `FormatError('attempts_exhausted')` when the attempts run out.
- **Errors**: invalid configuration raises `FormatError('invalid_format')`; oversized input raises `FormatError('input_too_large')`; exhausted attempts raise `FormatError('attempts_exhausted')` with the last issues.

## Quality contract

The package is a single import module with `py.typed` and no runtime dependencies outside the standard library. The test module `tests/test_response_format_enforcer.py` exercises the public API and asserts returned issues, error codes and re-ask behavior.

## Decisions

No ADR files are part of the provided source. The code records its decisions directly: CSV header equality, bounded row and issue counts, SQLite-only `EXPLAIN` validation with an authorizer, full-match regex, and a bounded feedback loop.
