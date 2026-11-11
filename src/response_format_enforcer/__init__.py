"""Validate LLM replies as CSV, read-only SQLite SELECT statements, or a full-match regex.

Public API:
    CsvFormat, SqlFormat, RegexFormat, Issue, validate, enforce, FormatError,
    Message, LLMPort, RecordedLLM, FakeLLM, RecordingExhaustedError
"""

from __future__ import annotations

import csv
import io
import logging
import math
import re
import sqlite3
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Literal, Protocol, TypedDict

__all__ = [
    "CsvFormat",
    "FakeLLM",
    "FormatError",
    "Issue",
    "LLMPort",
    "Message",
    "RecordedLLM",
    "RecordingExhaustedError",
    "RegexFormat",
    "SqlFormat",
    "enforce",
    "validate",
]

# Add a NullHandler to avoid "No handler found" warnings.
logging.getLogger(__name__).addHandler(logging.NullHandler())

# Default maximum number of characters for a reply before it is deemed too large.
DEFAULT_MAX_CHARS = 100_000


class Message(TypedDict):
    role: Literal["system", "user", "assistant"]
    content: str


class LLMPort(Protocol):
    def complete(self, messages: Sequence[Message], *, max_tokens: int) -> str: ...


class RecordingExhaustedError(Exception):
    """Raised when a RecordedLLM runs out of pre-recorded replies."""


@dataclass(frozen=True)
class Issue:
    """A single validation issue, addressed by a path-like string."""

    path: str
    message: str


class FormatError(Exception):
    """Base error for the library with a stable machine-readable ``code``."""

    def __init__(
        self,
        code: Literal["invalid_format", "input_too_large", "attempts_exhausted"],
        issues: list[Issue] | None = None,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.issues = issues if issues is not None else []


class RecordedLLM:
    """LLM double that returns pre-recorded replies in order."""

    def __init__(self, replies: Sequence[str]) -> None:
        self._replies = list(replies)
        self._index = 0

    def complete(self, messages: Sequence[Message], *, max_tokens: int) -> str:
        if self._index >= len(self._replies):
            raise RecordingExhaustedError("no more recorded replies")
        reply = self._replies[self._index]
        self._index += 1
        return reply


class FakeLLM:
    """LLM double that delegates to a callable."""

    def __init__(self, fn: Callable[[Sequence[Message]], str]) -> None:
        self._fn = fn

    def complete(self, messages: Sequence[Message], *, max_tokens: int) -> str:
        return self._fn(messages)


@dataclass(frozen=True)
class CsvFormat:
    """Format for CSV data with optional typed columns.

    The first row must equal ``columns`` exactly. Each data row must have the same
    number of cells. Typed cells are validated according to ``types``, a mapping
    of column name to one of ``'int'``, ``'float'``, ``'str'``, or ``'date'``.
    """

    columns: Sequence[str]
    types: Mapping[str, Literal["int", "float", "str", "date"]] = field(default_factory=dict)
    max_rows: int = 10_000

    def __post_init__(self) -> None:
        if not self.columns:
            raise FormatError("invalid_format")
        if self.max_rows <= 0:
            raise FormatError("invalid_format")
        column_set = set(self.columns)
        if not set(self.types.keys()).issubset(column_set):
            raise FormatError("invalid_format")
        allowed_types = {"int", "float", "str", "date"}
        if not set(self.types.values()).issubset(allowed_types):
            raise FormatError("invalid_format")
        # Ensure types is immutable (already a Mapping, but make a copy to freeze)
        object.__setattr__(self, "types", dict(self.types))


class SqlFormat:
    """Format for a single read-only SQLite SELECT statement (or WITH...SELECT).

    The schema is executed at construction time on a private in-memory database.
    Validation compiles the statement with EXPLAIN to ensure it is syntactically
    valid and does not attempt any write operations (enforced by an authorizer).
    """

    def __init__(self, schema_ddl: str) -> None:
        self._conn = sqlite3.connect(":memory:")
        try:
            self._conn.executescript(schema_ddl)
        except sqlite3.Error as exc:
            raise FormatError("invalid_format") from exc

        # Authorizer: allow only SELECT, READ, FUNCTION; deny everything else.
        def authorizer(
            action: int, arg1: str | None, arg2: str | None, dbname: str | None, source: str | None
        ) -> int:
            if action in (sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION):
                return sqlite3.SQLITE_OK
            return sqlite3.SQLITE_DENY

        self._conn.set_authorizer(authorizer)


@dataclass(frozen=True)
class RegexFormat:
    """Format for text that must fully match a regular expression."""

    pattern: str

    def __post_init__(self) -> None:
        try:
            re.compile(self.pattern)
        except re.error as exc:
            raise FormatError("invalid_format") from exc

    @property
    def _compiled(self) -> re.Pattern[str]:
        """The compiled pattern (``re`` caches compiled patterns)."""
        return re.compile(self.pattern)


def _extract_inner(text: str) -> str:
    """Extract inner content if the text is wrapped in a Markdown code fence.

    The fence is recognized as a line starting with three backticks (optionally
    followed by a language word) and a final line consisting of just three backticks.
    """
    stripped = text.strip()
    lines = stripped.splitlines()
    if len(lines) >= 2:
        first_line = lines[0].strip()
        last_line = lines[-1].strip()
        # First line: ``` optionally followed by letters
        if re.fullmatch(r"```[A-Za-z]*", first_line) and last_line == "```":
            return "\n".join(lines[1:-1])
    return stripped


def _validate_csv(fmt: CsvFormat, inner: str) -> list[Issue]:
    """Validate CSV data and return a list of issues (max 20)."""
    issues: list[Issue] = []
    reader = csv.reader(io.StringIO(inner))
    rows = list(reader)
    if not rows:
        issues.append(Issue("header", f"expected {list(fmt.columns)}, got []"))
        return issues
    header = rows[0]
    if header != list(fmt.columns):
        issues.append(Issue("header", f"expected {list(fmt.columns)}, got {header}"))
        return issues
    data_row_index = 0
    for row in rows[1:]:
        data_row_index += 1
        if data_row_index > fmt.max_rows:
            issues.append(Issue("$", "too many rows"))
            break
        if len(row) != len(fmt.columns):
            issues.append(
                Issue(f"row {data_row_index}", f"expected {len(fmt.columns)} cells, got {len(row)}")
            )
            if len(issues) >= 20:
                break
            continue
        for col_name, cell in zip(fmt.columns, row, strict=False):
            expected_type = fmt.types.get(col_name)
            if expected_type is None:
                continue
            valid = _validate_cell(cell, expected_type)
            if not valid:
                display = cell if len(cell) <= 50 else cell[:50]
                issues.append(
                    Issue(
                        f"row {data_row_index}.{col_name}",
                        f"expected {expected_type}, got '{display}'",
                    )
                )
                if len(issues) >= 20:
                    break
        if len(issues) >= 20:
            break
    return issues


def _validate_cell(cell: str, expected_type: str) -> bool:
    """Validate a single CSV cell against the expected type."""
    if expected_type == "int":
        return re.fullmatch(r"-?[0-9]+", cell) is not None
    elif expected_type == "float":
        try:
            value = float(cell)
        except ValueError:
            return False
        return math.isfinite(value)
    elif expected_type == "date":
        if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", cell) is None:
            return False
        try:
            from datetime import date

            date.fromisoformat(cell)
        except ValueError:
            return False
        return True
    elif expected_type == "str":
        return True
    raise FormatError("invalid_format")


def _validate_sql(fmt: SqlFormat, inner: str) -> list[Issue]:
    """Validate a single SQL statement and return a list of issues."""
    issues: list[Issue] = []
    stmt = inner.strip()
    # Remove one trailing semicolon if present.
    if stmt.endswith(";"):
        stmt = stmt[:-1].rstrip()
    # Only allow SELECT or WITH at the start (case-insensitive).
    if not re.match(r"^(SELECT|WITH)\b", stmt, re.IGNORECASE):
        issues.append(Issue("$", "not allowed: only read-only SELECT statements"))
        return issues
    try:
        # Compile the statement with EXPLAIN; never execute it.
        fmt._conn.execute("EXPLAIN " + stmt)
    except (sqlite3.ProgrammingError, sqlite3.Warning):
        issues.append(Issue("$", "multiple statements"))
    except sqlite3.Error as exc:
        msg = str(exc)
        if msg.startswith("not authorized"):
            issues.append(Issue("$", "not allowed: only read-only SELECT statements"))
        else:
            issues.append(Issue("$", msg[:200]))
    return issues


def _validate_regex(fmt: RegexFormat, inner: str) -> list[Issue]:
    """Validate that the text fully matches the regex pattern."""
    if fmt._compiled.fullmatch(inner):
        return []
    return [Issue("$", "does not fully match the pattern")]


def validate(
    fmt: CsvFormat | SqlFormat | RegexFormat, text: str, *, max_chars: int = DEFAULT_MAX_CHARS
) -> list[Issue]:
    """Validate ``text`` against ``fmt``.

    Returns a list of :class:`Issue` objects. Raises :class:`FormatError` with code
    ``'input_too_large'`` if the text exceeds ``max_chars`` characters.
    """
    if len(text) > max_chars:
        raise FormatError("input_too_large")
    inner = _extract_inner(text)
    if isinstance(fmt, CsvFormat):
        return _validate_csv(fmt, inner)
    elif isinstance(fmt, SqlFormat):
        return _validate_sql(fmt, inner)
    elif isinstance(fmt, RegexFormat):
        return _validate_regex(fmt, inner)
    else:
        # Should never happen due to type hints, but for safety.
        raise TypeError("unsupported format type")


def enforce(
    llm: LLMPort,
    messages: Sequence[Message],
    fmt: CsvFormat | SqlFormat | RegexFormat,
    *,
    max_attempts: int = 3,
    max_tokens: int = 1024,
    on_event: Callable[[dict[str, object]], None] | None = None,
) -> str:
    """Ask ``llm`` to produce a reply conforming to ``fmt``, retrying with feedback.

    Raises :class:`FormatError` with code ``'attempts_exhausted'`` if no valid reply
    is obtained within ``max_attempts``. Exceptions from ``llm.complete`` propagate
    unchanged.
    """
    if not 1 <= max_attempts <= 10:
        raise FormatError("invalid_format")
    if max_tokens <= 0:
        raise FormatError("invalid_format")
    current_messages = list(messages)
    for attempt in range(1, max_attempts + 1):
        reply = llm.complete(current_messages, max_tokens=max_tokens)
        if len(reply) > DEFAULT_MAX_CHARS:
            issues = [Issue("$", "reply too large")]
        else:
            try:
                issues = validate(fmt, reply)
            except FormatError as exc:
                if exc.code == "input_too_large":
                    issues = [Issue("$", "reply too large")]
                else:
                    raise
        valid = len(issues) == 0
        if on_event is not None:
            on_event({"event": "attempt", "n": attempt, "valid": valid, "issues": len(issues)})
        if valid:
            return reply
        if attempt == max_attempts:
            raise FormatError("attempts_exhausted", issues=issues)
        # Build feedback message.
        feedback_lines = ["Your previous reply was invalid:"]
        for issue in issues[:20]:
            feedback_lines.append(f"- {issue.path}: {issue.message}")
        feedback_content = "\n".join(feedback_lines)
        current_messages.append({"role": "assistant", "content": reply})
        current_messages.append({"role": "user", "content": feedback_content})
    # Should be unreachable, but for completeness.
    raise FormatError("attempts_exhausted")
