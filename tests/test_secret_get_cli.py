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
