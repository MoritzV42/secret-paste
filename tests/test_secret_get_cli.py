"""CLI-Verhalten von ``secret-get`` — inkl. der neuen ``--json`` /
``--print-path`` Ausgabemodi.

Der eigentliche Wert landet nie auf stdout — diese Tests pinnen das fest.
"""

from __future__ import annotations

import json

import pytest

import secret_get_cli as cli
import secret_paste_core as core


@pytest.fixture
def stored_key(isolated_dirs, fake_backend, monkeypatch):
    """Legt einen Credential an und stellt sicher, dass ein Backend verfügbar ist."""
    core.write_credential("BREVO_KEY", "sk-secret-123", ttl_hours=2, persist_to_vault=False)
    # default_backend() darf in der Test-Umgebung (ohne pywin32/keyring) nicht
    # hart abbrechen — wir tun so, als sei DPAPI verfügbar.
    monkeypatch.setattr(cli.cc, "default_backend", lambda: core.LocalDPAPIBackend())
    return "BREVO_KEY"


def test_default_output_unchanged(stored_key, capsys):
    """Ohne Flags bleibt die ``OK:``-Zeile exakt wie vorher (stabiler Vertrag)."""
    rc = cli.main([stored_key])
    out = capsys.readouterr().out
    assert rc == 0
    assert out.startswith(f"OK: {stored_key} available at ")
    assert "min TTL, source=" in out
    # Wert taucht nie auf stdout auf.
    assert "sk-secret-123" not in out


def test_print_path_outputs_only_path(stored_key, capsys):
    rc = cli.main([stored_key, "--print-path"])
    out = capsys.readouterr().out.strip()
    assert rc == 0
    # Genau eine Zeile, die auf den Temp-Pfad zeigt — kein "OK:" davor.
    assert "\n" not in out
    assert out.endswith("BREVO_KEY.val")
    assert not out.startswith("OK:")
    assert "sk-secret-123" not in out
    # Der ausgegebene Pfad existiert und enthält den Wert (Datei, nicht stdout).
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
    # ttl_remaining ist eine ganze Sekundenzahl knapp unter dem 5-Min-Fenster.
    assert isinstance(payload["ttl_remaining"], int)
    assert 0 < payload["ttl_remaining"] <= core.TMP_TTL_MINUTES * 60
    # Wert ist nie Teil des JSON.
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
    # Kein halbes JSON auf stdout, wenn der Key fehlt.
    assert out.strip() == ""
