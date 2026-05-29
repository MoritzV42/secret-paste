"""CLI tests for the secret-paste config-management flags.

These exercise only the early-exit config commands (--enable-remote /
--disable-remote / --show-config) and the "name required" guard, so no GUI
dialog is ever opened.
"""

from __future__ import annotations

import secret_paste_cli as cli
import secret_paste_core as core


def test_enable_remote_sets_flag(isolated_dirs, capsys):
    rc = cli.main(["--enable-remote"])
    assert rc == 0
    assert core.load_config()["remote_enabled"] is True
    assert "enabled" in capsys.readouterr().out


def test_disable_remote_clears_flag(isolated_dirs, capsys):
    core.set_remote_enabled(True)
    rc = cli.main(["--disable-remote"])
    assert rc == 0
    assert core.load_config()["remote_enabled"] is False
    assert "disabled" in capsys.readouterr().out


def test_show_config_prints_state(isolated_dirs, capsys):
    core.save_config({"remote_enabled": True, "remote_backend": "sops-age"})
    rc = cli.main(["--show-config"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "remote_enabled: True" in out
    assert "sops-age" in out


def test_name_required_without_config_flag(isolated_dirs, monkeypatch, capsys):
    # main() uses `argv or sys.argv[1:]`, so an empty arg list must be supplied
    # via sys.argv to represent a real "no arguments" invocation.
    monkeypatch.setattr("sys.argv", ["secret-paste"])
    rc = cli.main()
    assert rc == 1
    assert "key name is required" in capsys.readouterr().err


def test_enable_remote_warns_when_no_vault_detected(isolated_dirs, monkeypatch, capsys):
    monkeypatch.setattr(core, "detect_vaults", lambda: [])
    rc = cli.main(["--enable-remote"])
    assert rc == 0
    assert "no supported vault CLI" in capsys.readouterr().err
