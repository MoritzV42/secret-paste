"""``set_remote_backend`` + the ``--set-remote`` CLI command."""

from __future__ import annotations

import pytest

import secret_paste_cli as cli
import secret_paste_core as core


def test_set_remote_backend_stores_spec(isolated_dirs):
    cfg = core.set_remote_backend("sops-age", recipient="age1xyz")
    assert cfg["remote_backend"] == {"type": "sops-age", "recipient": "age1xyz"}
    assert core.load_config()["remote_backend"]["recipient"] == "age1xyz"


def test_set_remote_backend_drops_empty_options(isolated_dirs):
    cfg = core.set_remote_backend("sops-age", recipient="")
    assert cfg["remote_backend"] == {"type": "sops-age"}


def test_set_remote_backend_clear(isolated_dirs):
    core.set_remote_backend("sops-age", recipient="age1xyz")
    cfg = core.set_remote_backend(None)
    assert cfg["remote_backend"] is None


def test_set_remote_backend_unknown_type_raises(isolated_dirs):
    with pytest.raises(ValueError):
        core.set_remote_backend("totally-unknown")
    # Nothing persisted on failure.
    assert core.load_config()["remote_backend"] is None


def test_cli_set_remote_exits_zero_and_persists(isolated_dirs, capsys):
    rc = cli.main(["--set-remote", "sops-age", "--recipient", "age1abc"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "sops-age" in out
    assert core.load_config()["remote_backend"]["recipient"] == "age1abc"


def test_cli_set_remote_unknown_type_returns_1(isolated_dirs, capsys):
    rc = cli.main(["--set-remote", "nope"])
    err = capsys.readouterr().err
    assert rc == 1
    assert "Unknown remote backend" in err
