"""Behavior tests for the public API of response_format_enforcer."""

from __future__ import annotations

import pytest

import response_format_enforcer


def test_normalize_trims_and_lowercases() -> None:
    assert response_format_enforcer.normalize("  Hello World ") == "hello world"


@pytest.mark.parametrize("value", ["", "   ", "\t\n"])
def test_normalize_rejects_blank_input(value: str) -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        response_format_enforcer.normalize(value)


def test_version_is_semver() -> None:
    parts = response_format_enforcer.__version__.split(".")
    assert len(parts) == 3
    assert all(part.isdigit() for part in parts)
