"""Tests for the response_format_enforcer package."""

from __future__ import annotations

import pytest

from response_format_enforcer import (
    CsvFormat,
    FakeLLM,
    FormatError,
    Issue,
    Message,
    RecordedLLM,
    RecordingExhaustedError,
    RegexFormat,
    SqlFormat,
    enforce,
    validate,
)

# Helper constants
MAX_CHARS = 100_000


class RaisingLLM:
    """LLM double that raises a custom exception."""

    def complete(self, messages: list[Message], *, max_tokens: int) -> str:
        raise RuntimeError("boom")


@pytest.fixture
def csv_fmt() -> CsvFormat:
    return CsvFormat(["name", "qty"], types={"qty": "int"})


@pytest.fixture
def sql_fmt() -> SqlFormat:
    return SqlFormat("CREATE TABLE users(id INTEGER, name TEXT);")


@pytest.fixture
def regex_fmt() -> RegexFormat:
    return RegexFormat(r"[0-9]{4}-[0-9]{2}")


class TestCsvFormat:
    def test_construction_valid(self) -> None:
        fmt = CsvFormat(["a", "b"], types={"a": "int"}, max_rows=5)
        assert fmt.columns == ["a", "b"]
        assert fmt.types == {"a": "int"}
        assert fmt.max_rows == 5

    def test_construction_invalid_columns_empty(self) -> None:
        with pytest.raises(FormatError) as exc_info:
            CsvFormat([])
        assert exc_info.value.code == "invalid_format"

    def test_construction_invalid_types_key(self) -> None:
        with pytest.raises(FormatError) as exc_info:
            CsvFormat(["a"], types={"b": "int"})
        assert exc_info.value.code == "invalid_format"

    def test_construction_invalid_max_rows(self) -> None:
        with pytest.raises(FormatError) as exc_info:
            CsvFormat(["a"], max_rows=0)
        assert exc_info.value.code == "invalid_format"

    def test_construction_invalid_type_name(self) -> None:
        with pytest.raises(FormatError) as exc_info:
            CsvFormat(["qty"], types={"qty": "integer"})  # type: ignore[dict-item]
        assert exc_info.value.code == "invalid_format"

    def test_validate_empty(self, csv_fmt: CsvFormat) -> None:
        assert validate(csv_fmt, "") == [Issue("header", "expected ['name', 'qty'], got []")]

    def test_validate_header_correct(self, csv_fmt: CsvFormat) -> None:
        assert validate(csv_fmt, "name,qty\napple,3") == []

    def test_validate_header_wrong(self, csv_fmt: CsvFormat) -> None:
        result = validate(csv_fmt, "qty,name\n3,apple")
        assert result == [Issue("header", "expected ['name', 'qty'], got ['qty', 'name']")]

    def test_validate_invalid_cell_type(self, csv_fmt: CsvFormat) -> None:
        result = validate(csv_fmt, "name,qty\napple,3\npear,x")
        assert result == [Issue("row 2.qty", "expected int, got 'x'")]

    def test_validate_int_rejects_non_ascii_digits(self, csv_fmt: CsvFormat) -> None:
        result = validate(csv_fmt, "name,qty\napple,\u0663")
        assert result == [Issue("row 1.qty", "expected int, got '\u0663'")]

    def test_validate_date_rejects_fullwidth_digits(self) -> None:
        fmt = CsvFormat(["name", "day"], types={"day": "date"})
        cell = "\uff12\uff10\uff12\uff16-\uff11\uff11-\uff10\uff19"
        result = validate(fmt, "name,day\napple," + cell)
        assert result == [Issue("row 1.day", f"expected date, got '{cell}'")]

    def test_validate_wrong_number_of_cells(self, csv_fmt: CsvFormat) -> None:
        result = validate(csv_fmt, "name,qty\napple,3,extra")
        assert result == [Issue("row 1", "expected 2 cells, got 3")]

    def test_validate_fenced_content(self, csv_fmt: CsvFormat) -> None:
        # Fence with language word
        text = "```csv\nname,qty\napple,3\n```"
        assert validate(csv_fmt, text) == []
        # Fence without language word
        text2 = "```\nname,qty\napple,3\n```"
        assert validate(csv_fmt, text2) == []

    def test_validate_quoted_cell_with_comma(self) -> None:
        fmt = CsvFormat(["name", "qty"])
        text = 'name,qty\n"Doe, John",3'
        assert validate(fmt, text) == []

    def test_validate_max_rows_exceeded(self) -> None:
        fmt = CsvFormat(["a"], max_rows=1)
        text = "a\n1\n2"
        result = validate(fmt, text)
        assert result == [Issue("$", "too many rows")]

    def test_validate_issue_limit_20(self, csv_fmt: CsvFormat) -> None:
        # Create a CSV with more than 20 data rows, each with invalid int.
        rows = ["name,qty"]
        for i in range(30):
            rows.append(f"item{i},x")
        text = "\n".join(rows)
        result = validate(csv_fmt, text)
        assert len(result) == 20
        # All issues should be row N.qty expected int
        for issue in result:
            assert issue.path.endswith(".qty")
            assert issue.message == "expected int, got 'x'"

    def test_validate_input_too_large(self, csv_fmt: CsvFormat) -> None:
        long_text = "a" * (MAX_CHARS + 1)
        with pytest.raises(FormatError) as exc_info:
            validate(csv_fmt, long_text)
        assert exc_info.value.code == "input_too_large"
        assert exc_info.value.issues == []

    def test_validate_input_at_max(self, csv_fmt: CsvFormat) -> None:
        long_text = "a" * MAX_CHARS
        # This text is not valid CSV, but validate should not raise for length;
        # it will attempt to parse and return a header issue.
        result = validate(csv_fmt, long_text)
        assert isinstance(result, list)


class TestSqlFormat:
    def test_construction_valid(self) -> None:
        fmt = SqlFormat("CREATE TABLE t(a INT);")
        # Should not raise; the connection is stored.
        assert hasattr(fmt, "_conn")

    def test_construction_invalid_ddl(self) -> None:
        with pytest.raises(FormatError) as exc_info:
            SqlFormat("THIS IS NOT SQL;")
        assert exc_info.value.code == "invalid_format"

    def test_validate_select_from_existing_table(self, sql_fmt: SqlFormat) -> None:
        assert validate(sql_fmt, "SELECT name FROM users WHERE id = 1") == []

    def test_validate_with_query(self, sql_fmt: SqlFormat) -> None:
        stmt = "WITH x AS (SELECT 1) SELECT * FROM x"
        assert validate(sql_fmt, stmt) == []

    def test_validate_select_from_missing_table(self, sql_fmt: SqlFormat) -> None:
        result = validate(sql_fmt, "SELECT * FROM orders")
        assert result == [Issue("$", "no such table: orders")]

    def test_validate_delete_not_allowed(self, sql_fmt: SqlFormat) -> None:
        result = validate(sql_fmt, "DELETE FROM users")
        assert result == [Issue("$", "not allowed: only read-only SELECT statements")]

    def test_validate_multiple_statements(self, sql_fmt: SqlFormat) -> None:
        result = validate(sql_fmt, "SELECT 1; SELECT 2")
        assert result == [Issue("$", "multiple statements")]

    def test_validate_pragma_not_allowed(self, sql_fmt: SqlFormat) -> None:
        result = validate(sql_fmt, "PRAGMA table_info(users)")
        assert result == [Issue("$", "not allowed: only read-only SELECT statements")]

    def test_validate_attach_not_allowed(self, sql_fmt: SqlFormat) -> None:
        result = validate(sql_fmt, "ATTACH DATABASE ':memory:' AS aux")
        assert result == [Issue("$", "not allowed: only read-only SELECT statements")]

    def test_validate_authorizer_denies_write_in_with(self, sql_fmt: SqlFormat) -> None:
        # WITH ... DELETE should be denied by authorizer, even though starts with WITH.
        stmt = "WITH x AS (SELECT 1) DELETE FROM users"
        result = validate(sql_fmt, stmt)
        assert result == [Issue("$", "not allowed: only read-only SELECT statements")]

    def test_validate_error_truncation(self, sql_fmt: SqlFormat) -> None:
        # Create an error message longer than 200 chars by referring to a very long table name.
        long_name = "a" * 300
        stmt = " ".join(["SELECT", "*", "FROM", long_name])
        result = validate(sql_fmt, stmt)
        assert len(result) == 1
        assert result[0].path == "$"
        assert len(result[0].message) <= 200

    def test_no_statement_execution(self, sql_fmt: SqlFormat) -> None:
        # If validation were to execute, this would raise; it should just validate.
        # A SELECT that would cause an error at execution time (e.g., division by zero)
        # should still validate fine if schema allows.
        stmt = "SELECT 1/0"
        assert validate(sql_fmt, stmt) == []


class TestRegexFormat:
    def test_construction_valid(self) -> None:
        fmt = RegexFormat(r"\d+")
        assert fmt.pattern == r"\d+"

    def test_construction_invalid_pattern(self) -> None:
        with pytest.raises(FormatError) as exc_info:
            RegexFormat("(")
        assert exc_info.value.code == "invalid_format"

    def test_validate_match(self, regex_fmt: RegexFormat) -> None:
        assert validate(regex_fmt, "2026-11") == []

    def test_validate_no_match(self, regex_fmt: RegexFormat) -> None:
        result = validate(regex_fmt, "2026-11-09")
        assert result == [Issue("$", "does not fully match the pattern")]

    def test_validate_fenced(self, regex_fmt: RegexFormat) -> None:
        text = "```regex\n2026-11\n```"
        assert validate(regex_fmt, text) == []


class TestEnforce:
    def test_enforce_success_first_attempt(self, csv_fmt: CsvFormat) -> None:
        llm = RecordedLLM(["name,qty\napple,3"])
        messages: list[Message] = [{"role": "user", "content": "list fruit"}]
        result = enforce(llm, messages, csv_fmt)
        assert result == "name,qty\napple,3"
        # No additional messages added
        assert llm._index == 1

    def test_enforce_retry_with_feedback(self, csv_fmt: CsvFormat) -> None:
        replies = [
            "name,qty\napple,x",
            "name,qty\napple,3",
        ]
        llm = RecordedLLM(replies)
        messages: list[Message] = [{"role": "user", "content": "list fruit"}]
        result = enforce(llm, messages, csv_fmt)
        assert result == replies[1]
        # The second call should have received extra messages.
        assert llm._index == 2
        # We can't easily inspect the second call's passed messages because RecordedLLM
        # doesn't store them. Instead use FakeLLM to capture.
        captured_messages: list[list[Message]] = []

        def fake_fn(msgs: list[Message]) -> str:
            captured_messages.append(msgs.copy())
            if len(captured_messages) == 1:
                return "name,qty\napple,x"
            else:
                return "name,qty\napple,3"

        fake_llm = FakeLLM(fake_fn)
        result2 = enforce(fake_llm, messages, csv_fmt)
        assert result2 == "name,qty\napple,3"
        assert len(captured_messages) == 2
        second_call_msgs = captured_messages[1]
        # Should have original user message + assistant reply + feedback user message
        assert len(second_call_msgs) == 3
        assert second_call_msgs[0] == messages[0]
        assert second_call_msgs[1]["role"] == "assistant"
        assert second_call_msgs[1]["content"] == "name,qty\napple,x"
        feedback = second_call_msgs[2]
        assert feedback["role"] == "user"
        assert feedback["content"].startswith("Your previous reply was invalid:")
        assert "row 1.qty: expected int, got 'x'" in feedback["content"]

    def test_enforce_feedback_message_exact(self, csv_fmt: CsvFormat) -> None:
        # The second call's last message is {'role': 'user', 'content': ...}
        captured: list[list[Message]] = []

        def fn(msgs: list[Message]) -> str:
            captured.append(msgs.copy())
            if len(captured) == 1:
                return "name,qty\napple,x"
            return "name,qty\napple,3"

        messages: list[Message] = [{"role": "user", "content": "list fruit"}]
        result = enforce(FakeLLM(fn), messages, csv_fmt)
        assert result == "name,qty\napple,3"
        expected_feedback = "Your previous reply was invalid:\n- row 1.qty: expected int, got 'x'"
        assert captured[1][-1] == {"role": "user", "content": expected_feedback}

    def test_enforce_max_attempts_exhausted(self, csv_fmt: CsvFormat) -> None:
        llm = RecordedLLM(["name,qty\napple,x"] * 3)
        messages: list[Message] = [{"role": "user", "content": "list fruit"}]
        with pytest.raises(FormatError) as exc_info:
            enforce(llm, messages, csv_fmt, max_attempts=3)
        assert exc_info.value.code == "attempts_exhausted"
        issues = exc_info.value.issues
        assert len(issues) == 1
        assert issues[0] == Issue("row 1.qty", "expected int, got 'x'")

    def test_enforce_invalid_max_attempts(self, csv_fmt: CsvFormat) -> None:
        llm = RecordedLLM([])
        messages: list[Message] = []
        with pytest.raises(FormatError) as exc_info:
            enforce(llm, messages, csv_fmt, max_attempts=0)
        assert exc_info.value.code == "invalid_format"
        with pytest.raises(FormatError) as exc_info:
            enforce(llm, messages, csv_fmt, max_attempts=11)
        assert exc_info.value.code == "invalid_format"

    def test_enforce_llm_exception_propagates(self, csv_fmt: CsvFormat) -> None:
        llm = RaisingLLM()
        messages: list[Message] = [{"role": "user", "content": "test"}]
        with pytest.raises(RuntimeError, match="boom"):
            enforce(llm, messages, csv_fmt)

    def test_enforce_reply_too_large(self, csv_fmt: CsvFormat) -> None:
        large_reply = "a" * (MAX_CHARS + 1)
        captured: list[list[Message]] = []
        events: list[dict[str, object]] = []

        def fn(msgs: list[Message]) -> str:
            captured.append(list(msgs))
            if len(captured) == 1:
                return large_reply
            return "name,qty\napple,3"

        messages: list[Message] = [{"role": "user", "content": "list fruit"}]
        result = enforce(FakeLLM(fn), messages, csv_fmt, on_event=events.append)
        assert result == "name,qty\napple,3"
        assert events[0] == {"event": "attempt", "n": 1, "valid": False, "issues": 1}
        assert captured[1][-1] == {
            "role": "user",
            "content": "Your previous reply was invalid:\n- $: reply too large",
        }

    def test_enforce_on_event_payloads(self, csv_fmt: CsvFormat) -> None:
        replies = ["name,qty\napple,x", "name,qty\napple,3"]
        llm = RecordedLLM(replies)
        events: list[dict[str, object]] = []

        def event_cb(payload: dict[str, object]) -> None:
            events.append(payload.copy())

        messages: list[Message] = [{"role": "user", "content": "list fruit"}]
        result = enforce(llm, messages, csv_fmt, on_event=event_cb)
        assert result == replies[1]
        assert len(events) == 2
        first_event = events[0]
        assert first_event == {"event": "attempt", "n": 1, "valid": False, "issues": 1}
        second_event = events[1]
        assert second_event == {"event": "attempt", "n": 2, "valid": True, "issues": 0}
        # Events must not contain reply text or messages
        for event in events:
            assert "reply" not in event
            assert "messages" not in event

    def test_enforce_with_sql_format(self, sql_fmt: SqlFormat) -> None:
        llm = RecordedLLM(["SELECT * FROM orders", "SELECT name FROM users WHERE id = 1"])
        messages: list[Message] = [{"role": "user", "content": "query users"}]
        result = enforce(llm, messages, sql_fmt)
        assert result == "SELECT name FROM users WHERE id = 1"

    def test_enforce_with_regex_format(self, regex_fmt: RegexFormat) -> None:
        llm = RecordedLLM(["2026", "2026-11"])
        messages: list[Message] = [{"role": "user", "content": "date"}]
        result = enforce(llm, messages, regex_fmt)
        assert result == "2026-11"


class TestLLMDoubles:
    def test_recorded_llm_returns_in_order(self) -> None:
        replies = ["a", "b", "c"]
        llm = RecordedLLM(replies)
        assert llm.complete([], max_tokens=10) == "a"
        assert llm.complete([], max_tokens=10) == "b"
        assert llm.complete([], max_tokens=10) == "c"
        with pytest.raises(RecordingExhaustedError):
            llm.complete([], max_tokens=10)

    def test_fake_llm_calls_function(self) -> None:
        captured: list[list[Message]] = []

        def fn(msgs: list[Message]) -> str:
            captured.append(msgs.copy())
            return "reply"

        llm = FakeLLM(fn)
        msgs: list[Message] = [{"role": "user", "content": "hello"}]
        assert llm.complete(msgs, max_tokens=5) == "reply"
        assert len(captured) == 1
        assert captured[0] == msgs


class TestErrors:
    def test_format_error_attributes(self) -> None:
        issues = [Issue("$", "bad")]
        err = FormatError("attempts_exhausted", issues)
        assert err.code == "attempts_exhausted"
        assert err.issues == issues
        err2 = FormatError("invalid_format")
        assert err2.code == "invalid_format"
        assert err2.issues == []

    def test_issue_is_frozen(self) -> None:
        issue = Issue("path", "msg")
        with pytest.raises(AttributeError):
            issue.path = "other"  # type: ignore[attr-defined]
