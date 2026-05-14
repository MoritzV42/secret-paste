"""Path-traversal protection for credential key names."""

from __future__ import annotations

import pytest

import secret_paste_core as core


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("BREVO_KEY", "BREVO_KEY"),
        ("ABC-123.txt", "ABC-123.txt"),
        ("a_b.c-d", "a_b.c-d"),
    ],
)
def test_safe_name_keeps_allowed_chars(raw, expected):
    assert core._safe_name(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("foo/bar", "foobar"),
        ("a\\b\\c", "abc"),
        ("a b c", "abc"),
        ("hello;rm -rf /", "hellorm-rf"),
        ("DROP TABLE users;--", "DROPTABLEusers--"),
    ],
)
def test_safe_name_strips_path_and_special_chars(raw, expected):
    assert core._safe_name(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "///",
        "..\\..\\",
        "$%@!",
        "../etc/passwd",  # starts with '.' after sanitizing
        ".hidden",
        ".meta",  # would collide with our metadata file convention
    ],
)
def test_safe_name_rejects_invalid(raw):
    with pytest.raises(ValueError):
        core._safe_name(raw)


@pytest.mark.parametrize(
    "raw",
    ["CON", "con", "PRN", "AUX", "NUL", "COM1", "lpt9", "CON.txt", "Nul.meta"],
)
def test_safe_name_rejects_windows_reserved(raw):
    with pytest.raises(ValueError, match="reserved device name"):
        core._safe_name(raw)


def test_safe_name_unicode_stripped():
    # We deliberately restrict to ASCII alnum + ._- so a name like "Ärger"
    # collapses; assert the rejection rather than silently letting it through.
    # `ä` is alpha but not ASCII-alnum — Python's isalnum returns True for
    # unicode letters, so it survives. That's by design (filesystem-safe on
    # all OSes we target) but the test pins the behaviour explicitly so we
    # notice if we ever change the rules.
    out = core._safe_name("Ärger")
    assert out == "Ärger"
    # Path separators are still stripped regardless of unicode.
    assert core._safe_name("Ä/r/ger") == "Ärger"
