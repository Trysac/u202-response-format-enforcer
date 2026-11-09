# Usage Guide for response_format_enforcer

This library validates LLM replies that must conform to CSV, SQL, or regex formats, and can automatically re-ask the model with feedback when validation fails.

## CSV Validation

```python
from response_format_enforcer import CsvFormat, validate, Issue

# Define expected columns and types.
fmt = CsvFormat(
    columns=["name", "qty", "unit_price", "order_date"],
    types={"qty": "int", "unit_price": "float", "order_date": "date"},
    max_rows=1000,
)

# Valid CSV
valid_text = "name,qty,unit_price,order_date\napple,10,0.5,2025-01-15"
assert validate(fmt, valid_text) == []

# Invalid: qty not int, unit_price not float, date wrong format
invalid_text = "name,qty,unit_price,order_date\napple,x,abc,2025/01/15"
issues = validate(fmt, invalid_text)
for issue in issues:
    print(f"{issue.path}: {issue.message}")
# Output:
# row 1.qty: expected int, got 'x'
# row 1.unit_price: expected float, got 'abc'
# row 1.order_date: expected date, got '2025/01/15'
```

Markdown code fences are stripped automatically:

```python
fenced = "```csv\nname,qty,unit_price,order_date\napple,3,0.5,2025-01-15\n```"
assert validate(fmt, fenced) == []
```

## SQL Validation

Provide a schema DDL that is executed on a private in-memory SQLite database.

```python
from response_format_enforcer import SqlFormat, validate

schema = """
CREATE TABLE products (
    id INTEGER PRIMARY KEY,
    name TEXT,
    price REAL
);
"""
sql_fmt = SqlFormat(schema)

# Allowed: read-only SELECT
assert validate(sql_fmt, "SELECT id, name FROM products WHERE price > 10") == []

# Denied: write operations
issues = validate(sql_fmt, "DELETE FROM products")
assert issues == [Issue("$", "not allowed: only read-only SELECT statements")]

# Denied: multiple statements
issues = validate(sql_fmt, "SELECT 1; SELECT 2")
assert issues == [Issue("$", "multiple statements")]

# Missing table reported verbatim (truncated to 200 chars)
issues = validate(sql_fmt, "SELECT * FROM missing_table")
assert issues == [Issue("$", "no such table: missing_table")]
```

## Regex Validation

```python
from response_format_enforcer import RegexFormat, validate

regex_fmt = RegexFormat(r"\d{4}-\d{2}-\d{2}")  # YYYY-MM-DD

assert validate(regex_fmt, "2025-01-15") == []
assert validate(regex_fmt, "2025/01/15") == [Issue("$", "does not fully match the pattern")]
```

## Enforcement with Re-ask Loop

Use `enforce()` to ask an LLM to produce a conforming reply. It will retry up to `max_attempts` (default 3), feeding back validation issues.

```python
from response_format_enforcer import enforce, RecordedLLM, CsvFormat

fmt = CsvFormat(["name", "qty"], types={"qty": "int"})

# Simulate an LLM that first returns an invalid reply, then a valid one.
llm = RecordedLLM(["name,qty\napple,x", "name,qty\napple,3"])
messages = [{"role": "user", "content": "List fruits with quantities."}]

result = enforce(llm, messages, fmt)
print(result)  # name,qty\napple,3
```

The second LLM call receives the following additional messages:
- assistant: `name,qty\napple,x`
- user: `Your previous reply was invalid:\n- row 1.qty: expected int, got 'x'`

If all attempts fail, `FormatError` with code `'attempts_exhausted'` is raised.

## Error Handling

All library-specific errors derive from `FormatError`. Constants for codes:

- `'invalid_format'` – bad format specification (e.g., invalid regex, bad DDL).
- `'input_too_large'` – input exceeds `max_chars` (default 100_000) in `validate()`.
- `'attempts_exhausted'` – no valid reply after `max_attempts` in `enforce()`.

`RecordedLLM` raises `RecordingExhaustedError` if called beyond its recorded replies.

## Event Hook

`enforce()` accepts an `on_event` callback that receives a dictionary with keys `event`, `n`, `valid`, `issues` (count). It never contains reply text or messages.

```python
events = []


def log_event(payload):
    events.append(payload)


enforce(llm, messages, fmt, on_event=log_event)
print(events)  # e.g., [{'event': 'attempt', 'n': 1, 'valid': False, 'issues': 1}, ...]
```
