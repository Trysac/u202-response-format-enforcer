# Project record

## Objective

Validate LLM replies as CSV with typed columns, read-only SQLite SELECT statements or a full-match regex, and re-ask with a bounded correction loop.

## Scope

- In scope: CSV validation with exact header matching, typed cells (`int`, `float`, `str`, `date`), `max_rows` and at most 20 issues.
- In scope: read-only SQLite `SELECT` or `WITH` validation against a caller-supplied schema, using `EXPLAIN` and an authorizer; statements are never executed.
- In scope: full-match regex validation with `re.fullmatch`.
- In scope: extraction of content inside a Markdown code fence before validation.
- In scope: `enforce()` with bounded attempts, feedback messages and `on_event` payloads.
- Out of scope: JSON and YAML validation; JSON has mature validators and YAML would need a parser dependency.
- Out of scope: SQL dialects other than SQLite.
- Out of scope: executing SQL queries.

## Timeline

The provided source contains no release dates or changelog.

## Effort metrics

Measured values only; a value that has not been measured stays "pending measurement".

| Metric | Value |
|---|---|
| Tokens (input / output) | 967861 / 63731 |
| Hours (human) | pending measurement |
| Cost (USD) | 0.0980 |

## Factory run u202 (measured from API usage)

| Phase | Model | Batch | Input | Output | Cache write | Cache read | Cost (USD) |
|---|---|---|---|---|---|---|---|
| generation | deepseek-v4-pro | yes | 1914 | 20155 | 0 | 3328 | 0.0412 |
| fix-1 | deepseek-flash | no | 10639 | 5202 | 0 | 69248 | 0.0049 |
| fix-2 | deepseek-flash | no | 8266 | 1542 | 0 | 25728 | 0.0022 |
| fix-3 | deepseek-flash | no | 8580 | 2343 | 0 | 40320 | 0.0028 |
| audit | deepseek-flash | no | 30179 | 21022 | 0 | 404864 | 0.0184 |
| fix-4 | deepseek-flash | no | 24548 | 4556 | 0 | 233344 | 0.0071 |
| docs | deepseek-flash | no | 106647 | 8911 | 0 | 256 | 0.0213 |

Total: $0.0980. Prices: deepseek line, as measured by its adapter.
