# Stack

## Used

| Tool | Why |
|---|---|
| Python >= 3.10 | The code uses PEP 604 unions, built-in generics, `dataclasses`, `typing.Protocol`, `typing.TypedDict` and `zip(strict=False)`. |
| `csv` | Parses CSV with the standard library default dialect. |
| `re` | Validates full-match regex formats and typed CSV cells. |
| `sqlite3` | Compiles SQL statements with `EXPLAIN` on a private `:memory:` connection and enforces a read-only authorizer. |
| `pytest` | The test module `tests/test_response_format_enforcer.py` uses pytest-style tests and `pytest.raises`. |

## Discarded

| Tool | Why not |
|---|---|
| JSON and YAML validators | Out of scope: JSON has mature validators and YAML would need a parser dependency. |
| Non-SQLite SQL dialects | `SqlFormat` is built on `sqlite3`; other dialects are out of scope. |
| Executing SQL | Validation uses `EXPLAIN` only and never executes the statement. |
