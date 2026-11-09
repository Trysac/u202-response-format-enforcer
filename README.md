# response-format-enforcer

[![PyPI version](https://img.shields.io/pypi/v/trysac-response-format-enforcer)](https://pypi.org/project/trysac-response-format-enforcer/)
[![License: MIT](https://img.shields.io/pypi/l/trysac-response-format-enforcer)](LICENSE)
[![CI](https://github.com/Trysac/u202-response-format-enforcer/actions/workflows/ci.yml/badge.svg)](https://github.com/Trysac/u202-response-format-enforcer/actions/workflows/ci.yml)

Validate LLM replies as CSV with typed columns, read-only SQLite SELECT statements or a full-match regex, and re-ask with a bounded correction loop

## Problem

Describe in two or three sentences the concrete problem this utility solves, who hits it, and what
they do today without it. Replace this paragraph when the first real feature lands.

## Install

```sh
pip install trysac-response-format-enforcer
# or
uv add trysac-response-format-enforcer
```

Requires Python 3.10 or newer. No runtime dependencies.

## Usage

```python
import response_format_enforcer

# normalize() trims surrounding whitespace and lower-cases the text.
print(response_format_enforcer.normalize("  Hello World "))  # -> "hello world"

# Blank input is rejected explicitly instead of returning an empty string.
try:
    response_format_enforcer.normalize("   ")
except ValueError as exc:
    print(f"rejected: {exc}")
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md) and [decisions](docs/decisions/)
- [Testing](docs/TESTING.md) and [security](docs/SECURITY.md)
- [Project record](docs/PROJECT.md) and [stack](docs/STACK.md)
- [Changelog](CHANGELOG.md) and [contributing guide](CONTRIBUTING.md)

## License

[MIT](LICENSE) (c) 2026 Miguel Gomez
