"""CLI behaviour of ``secret-get`` — including the new ``--json`` /
``--print-path`` output modes.

The actual value never reaches stdout — these tests pin that down.
"""

from __future__ import annotations

import json

import pytest

import secret_get_cli as cli
import secret_paste_core as core


@pytest.fixture
def stored_key(isolated_dirs, fake_backend, monkeypatch):
    """Store a credential and make sure a backend is available."""
    core.write_credential("BREVO_KEY", "sk-secret-123", ttl_hours=2, persist_to_vault=False)
    # default_backend() must not hard-fail in the test environment (no
    # pywin32/keyring) — pretend DPAPI is available.
    monkeypatch.setattr(cli.cc, "default_backend", lambda: core.LocalDPAPIBackend())
    return "BREVO_KEY"


def test_default_output_unchanged(stored_key, capsys):
    """Without flags the ``OK:`` line stays exactly as before (stable contract)."""
    rc = cli.main([stored_key])
    out = capsys.readouterr().out
    assert rc == 0
    assert out.startswith(f"OK: {stored_key} available at ")
    assert "min TTL, source=" in out
    # The value never appears on stdout.
    assert "sk-secret-123" not in out


def test_print_path_outputs_only_path(stored_key, capsys):
    rc = cli.main([stored_key, "--print-path"])
    out = capsys.readouterr().out.strip()
    assert rc == 0
    # Exactly one line pointing at the temp path — no "OK:" prefix.
    assert "\n" not in out
    assert out.endswith("BREVO_KEY.val")
    assert not out.startswith("OK:")
    assert "sk-secret-123" not in out
    # The printed path exists and holds the value (file, not stdout).
    from pathlib import Path

    assert Path(out).read_text(encoding="utf-8") == "sk-secret-123"


def test_json_output_shape(stored_key, capsys):
    rc = cli.main([stored_key, "--json"])
    out = capsys.readouterr().out.strip()
    assert rc == 0
    payload = json.loads(out)
    assert set(payload) == {"name", "path", "ttl_remaining"}
    assert payload["name"] == "BREVO_KEY"
    assert payload["path"].endswith("BREVO_KEY.val")
    # ttl_remaining is a whole-second count just below the 5-minute window.
    assert isinstance(payload["ttl_remaining"], int)
    assert 0 < payload["ttl_remaining"] <= core.TMP_TTL_MINUTES * 60
    # The value is never part of the JSON.
    assert "sk-secret-123" not in out


def test_json_and_print_path_are_mutually_exclusive(stored_key):
    with pytest.raises(SystemExit):
        cli.main([stored_key, "--json", "--print-path"])


def test_export_env_conflicts_with_json(stored_key, capsys):
    rc = cli.main([stored_key, "--json", "--export-env"])
    err = capsys.readouterr().err
    assert rc == 1
    assert "--export-env" in err


def test_missing_key_returns_2_in_json_mode(isolated_dirs, fake_backend, monkeypatch, capsys):
    monkeypatch.setattr(cli.cc, "default_backend", lambda: core.LocalDPAPIBackend())
    rc = cli.main(["NOPE", "--json"])
    out = capsys.readouterr().out
    assert rc == 2
    # No half-written JSON on stdout when the key is missing.
    assert out.strip() == ""


# ---------------------------------------------------------------------------
# Multiline / dotenv (.env-block) support — issue #4.
# ---------------------------------------------------------------------------

# A representative dotenv block. The "values" here are deliberately NOT real
# secrets — they're placeholder tokens used only to assert structural parsing
# and that values are never interpolated into the emitted snippet.
_DOTENV_BLOCK = (
    "# leading comment\n"
    "FOO=bar\n"
    "\n"
    "  export BAZ = qux \n"
    "WITH_EQ=a=b=c\n"
    "   # indented comment\n"
    "EMPTY=\n"
    "noeqline\n"
    "=novalue\n"
)


def test_parse_dotenv_skips_blanks_and_comments():
    pairs = cli._parse_dotenv_lines(_DOTENV_BLOCK)
    keys = [k for k, _ in pairs]
    # Comments, blank lines, the no-'=' line and the empty-key line are skipped.
    assert keys == ["FOO", "BAZ", "WITH_EQ", "EMPTY"]


def test_parse_dotenv_splits_on_first_equals():
    pairs = dict(cli._parse_dotenv_lines(_DOTENV_BLOCK))
    assert pairs["WITH_EQ"] == "a=b=c"  # only the FIRST '=' splits
    assert pairs["EMPTY"] == ""


def test_parse_dotenv_strips_export_prefix_and_key_whitespace():
    pairs = dict(cli._parse_dotenv_lines(_DOTENV_BLOCK))
    # "  export BAZ = qux " -> key "BAZ" (export stripped, key trimmed).
    assert "BAZ" in pairs


def test_parse_dotenv_empty_input():
    assert cli._parse_dotenv_lines("") == []
    assert cli._parse_dotenv_lines("\n\n# only comments\n") == []


def _emit(env_name, path, shell, value):
    return cli._emit_export(env_name, path, shell, value)


def test_export_env_singleline_posix_unchanged():
    """A single-line value keeps the historical POSIX snippet exactly."""
    snip = _emit("FOO", "/tmp/foo.val", "posix", "single-line-value")
    assert "IFS= read -r FOO < /tmp/foo.val" in snip
    assert "export FOO" in snip
    assert "while" not in snip  # not the dotenv loop
    # The value never appears in the snippet.
    assert "single-line-value" not in snip
    assert "# File TTL:" in snip


def test_export_env_singleline_ps_unchanged():
    snip = _emit("FOO", r"C:\tmp\foo.val", "ps", "single-line-value")
    assert "Get-Content -Raw -Encoding UTF8" in snip
    assert "$env:FOO" in snip
    assert "foreach" not in snip
    assert "single-line-value" not in snip


def test_export_env_multiline_posix_uses_readloop_no_values():
    snip = _emit("ZWW_ENVS", "/tmp/zww.val", "posix", _DOTENV_BLOCK)
    # A read-loop over the file, not a single IFS= read of the first line.
    assert "while IFS= read -r line" in snip
    assert 'done < /tmp/zww.val' in snip
    assert "export " in snip
    # Crucially: NONE of the values from the block are in the snippet.
    for val in ("bar", "qux", "a=b=c"):
        assert val not in snip
    assert "# File TTL:" in snip


def test_export_env_multiline_ps_uses_readloop_no_values():
    snip = _emit("ZWW_ENVS", r"C:\tmp\zww.val", "ps", _DOTENV_BLOCK)
    assert "foreach ($line in (Get-Content" in snip
    assert "Set-Item -Path env:$k" in snip
    for val in ("bar", "qux", "a=b=c"):
        assert val not in snip
    assert "# File TTL:" in snip


@pytest.fixture
def stored_multiline(isolated_dirs, fake_backend, monkeypatch):
    core.write_credential(
        "ZWW_ENVS", _DOTENV_BLOCK, ttl_hours=2, persist_to_vault=False
    )
    monkeypatch.setattr(cli.cc, "default_backend", lambda: core.LocalDPAPIBackend())
    return "ZWW_ENVS"


def test_export_env_endtoend_multiline_value_not_on_stdout(stored_multiline, capsys):
    rc = cli.main([stored_multiline, "--export-env", "--shell=posix"])
    out = capsys.readouterr().out
    assert rc == 0
    # The dotenv loop is emitted and no value leaks to stdout.
    assert "while IFS= read -r line" in out
    for val in ("bar", "qux", "a=b=c"):
        assert val not in out
    # But the value IS written to the temp file (read by the snippet at eval).
    tmp = core.write_tmp_value(stored_multiline, _DOTENV_BLOCK)
    from pathlib import Path

    assert "FOO=bar" in Path(tmp).read_text(encoding="utf-8")
