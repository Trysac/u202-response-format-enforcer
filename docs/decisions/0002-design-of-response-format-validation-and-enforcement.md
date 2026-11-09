# Design of response format validation and enforcement

Status: accepted (generated, pending human review)

## Context

LLM replies requiring structured formats (CSV, SQL, regex) often have subtle errors. Existing solutions are ad-hoc and lack a standardized re-ask loop.

## Decision

Implement a library that provides focused validators per format, producing path-addressed issues, and an enforcement loop that feeds these issues back to the LLM up to a bounded number of attempts.

## Consequences

Pros: library-free (stdlib only) validation, consistent error structure, bounded retries. Cons: SQL validation limited to SQLite and read-only; regex catastrophic backtracking remains caller's responsibility (documented).
