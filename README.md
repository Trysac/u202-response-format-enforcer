# trysac-response-format-enforcer

[![PyPI version](https://badge.fury.io/py/trysac-response-format-enforcer.svg)](https://badge.fury.io/py/trysac-response-format-enforcer)
[![Python versions](https://img.shields.io/pypi/pyversions/trysac-response-format-enforcer.svg)](https://pypi.org/project/trysac-response-format-enforcer/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

LLM replies that must be CSV, a SQL query or a value matching a pattern are often almost right: a missing column, a non-numeric cell, a query against a table that does not exist. JSON has mature validation tools, but these formats get ad hoc parsing and unbounded retries. This library validates each format with exact, path-addressed issues and runs a bounded re-ask loop that feeds the issues back to the model.

## Installation

```bash
pip install trysac-response-format-enforcer
```

## Quick Example

```python
from response_format_enforcer import CsvFormat, validate, RecordedLLM, enforce

fmt = CsvFormat(["name", "qty"], types={"qty": "int"})
print(validate(fmt, "name,qty\napple,3"))
print(validate(fmt, "name,qty\napple,x"))

llm = RecordedLLM(["name,qty\napple,x", "name,qty\napple,3"])
result = enforce(llm, [{"role": "user", "content": "list fruit"}], fmt)
print(result)
```

## Features

- **Public API**: `CsvFormat`, `SqlFormat`, `RegexFormat`, `Issue`, `validate`, `enforce`, `FormatError`, `Message`, `LLMPort`, `RecordedLLM`, `FakeLLM`, `RecordingExhaustedError`.
- **CSV**: the first row must equal `columns` exactly; each data row must have the same number of cells; typed cells use `'int'` (`-?[0-9]+`), `'float'` (finite), `'date'` (`YYYY-MM-DD` and valid for `date.fromisoformat`) or `'str'` (anything); `max_rows` defaults to 10,000 and at most 20 issues are reported.
- **SQL**: `SqlFormat(schema_ddl)` executes the DDL on a private `sqlite3` `:memory:` connection at construction; validation accepts only a single `SELECT` or `WITH` statement, compiles it with `EXPLAIN`, never executes it, and uses an authorizer that allows only `SQLITE_SELECT`, `SQLITE_READ` and `SQLITE_FUNCTION`.
- **Regex**: `RegexFormat(pattern)` validates with `re.fullmatch`; the pattern is trusted caller input, so catastrophic backtracking is the caller's responsibility.
- **Fenced replies**: when the stripped reply starts with a line of three backticks (optionally followed by a language word) and ends with three backticks, only the inner lines are validated.
- **Bounded re-ask**: `enforce()` calls `llm.complete(messages, max_tokens=...)`, validates the reply, and on issues appends the assistant reply plus a user feedback message with one `- <path>: <message>` line per issue (at most 20) before retrying.
- **Errors**: `FormatError` carries `code` as `'invalid_format'`, `'input_too_large'` or `'attempts_exhausted'` and an `issues` list.
- **Limits and options**: `validate(..., max_chars=100_000)` raises `FormatError('input_too_large')` above the limit; `enforce(..., max_attempts=3, max_tokens=1024, on_event=None)` accepts `max_attempts` from 1 to 10; `on_event` receives payloads with exactly the keys `event`, `n`, `valid` and `issues`, never the reply text or the messages.

## Why not hand parsing

Hand parsing tends to produce vague errors and unbounded retries. This library returns exact, path-addressed `Issue` values such as `row 2.qty` or `header`, and `enforce()` is a bounded loop that feeds those issues back to the model.

## Documentation

See [docs/SECURITY.md](docs/SECURITY.md) for the threat model and limits, [docs/PROJECT.md](docs/PROJECT.md) for scope, and [docs/TESTING.md](docs/TESTING.md) for the test layout.

## License

MIT
