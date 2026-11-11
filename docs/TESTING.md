# Testing

## Running

```sh
python -m pytest tests/test_response_format_enforcer.py
```

## Policy

The tests are plain pytest tests in `tests/test_response_format_enforcer.py`. They import the public package (`CsvFormat`, `SqlFormat`, `RegexFormat`, `validate`, `enforce`, `FormatError`, `Issue`, `Message`, `RecordedLLM`, `RecordingExhaustedError`, `FakeLLM`) and assert returned `Issue` lists, raised `FormatError` codes, and re-ask behavior. The test module uses local objects only; no network calls or external services are present.

## Tiers

There is one test file, `tests/test_response_format_enforcer.py`, run locally. No separate conformance tier or marker-based selection is present in the provided test source.

## Layout

`tests/test_response_format_enforcer.py` contains `TestCsvFormat`, `TestSqlFormat` and the other pytest classes in that module. The CSV tests cover construction validation, empty input, correct and wrong headers, invalid cell types, non-ASCII digits for `int`, full-width digits for `date`, wrong cell counts, fenced content, quoted cells with commas, `max_rows`, the 20-issue limit, `max_chars` above and at the limit. The SQL tests cover valid construction, invalid DDL, `SELECT` on an existing table, `WITH` queries, and missing tables. The same module imports the regex, enforcement and LLM-double names listed above for their public API tests.
