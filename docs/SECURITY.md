# Security notes

## Threat model

`response_format_enforcer` is a pure library with no runtime dependencies and no network or filesystem I/O. It opens a private `sqlite3` `:memory:` connection only inside `SqlFormat`.

**Defended:**

- SQL writes are blocked by an authorizer that allows only `SQLITE_SELECT`, `SQLITE_READ` and `SQLITE_FUNCTION`; other actions return `SQLITE_DENY`.
- SQL statements are compiled with `conn.execute('EXPLAIN ' + statement)` and are never executed.
- A statement must start with `SELECT` or `WITH`; one trailing semicolon is allowed; multiple statements are rejected.
- `validate()` rejects input longer than `max_chars` (default 100,000) with `FormatError('input_too_large')`.
- CSV validation caps data rows with `max_rows` (default 10,000) and reports at most 20 issues.
- `enforce()` caps attempts from 1 to 10 and treats a reply over `DEFAULT_MAX_CHARS` as `Issue('$', 'reply too large')`.
- SQLite error messages are truncated to 200 characters when reported.
- `on_event` payloads contain only `event`, `n`, `valid` and `issues`; they do not contain the reply text or the messages.

**Not defended:**

- `RegexFormat` trusts the caller's pattern. `re.fullmatch` has no timeout; catastrophic backtracking is the caller's responsibility.
- SQL validation is limited to SQLite syntax and the caller-supplied schema. It does not sandbox SQLite extensions or cover other SQL dialects.
- Type checks are format checks, not business-rule validation: `int` accepts any `-?[0-9]+`, `float` accepts any finite Python float, and `str` accepts any text.
- The library does not redact issue messages beyond the stated SQLite 200-character truncation and the CSV cell display limit of 50 characters.
- The library does not authenticate or sandbox the `LLMPort` implementation; exceptions from `llm.complete()` propagate unchanged.

## Publishing

The provided source contains no credentials, tokens or publishing configuration. This file is the security note linked from the README.
