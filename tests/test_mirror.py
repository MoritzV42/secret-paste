"""Mirror-on-write behaviour with remote error isolation.

These tests verify that ``write_credential(..., persist_to_vault=True)``:

* only mirrors when remote is enabled AND a backend is configured,
* pushes to the configured remote backend when it should,
* never lets a remote failure corrupt the local store.
"""

from __future__ import annotations

import secret_paste_core as core


def test_no_mirror_when_remote_disabled(isolated_dirs, fake_backend, monkeypatch):
    store, _tmp = isolated_dirs
    core.save_config({"remote_enabled": False, "remote_backend": {"type": "sops-age"}})

    calls = []
    monkeypatch.setattr(
        core, "configured_remote_backend", lambda cfg=None: calls.append("built") or None
    )

    core.write_credential("KEY1", "v", ttl_hours=None, persist_to_vault=True)
    # Disabled short-circuits before the backend is ever built.
    assert calls == []
    # Local value is present.
    assert fake_backend["KEY1"] == "v"


def test_no_mirror_when_no_backend_configured(isolated_dirs, fake_backend):
    core.save_config({"remote_enabled": True, "remote_backend": None})
    # Should not raise; nothing to mirror to.
    core.write_credential("KEY2", "v", ttl_hours=None, persist_to_vault=True)
    assert fake_backend["KEY2"] == "v"


def test_no_mirror_when_persist_to_vault_false(isolated_dirs, fake_backend, monkeypatch):
    core.save_config({"remote_enabled": True, "remote_backend": {"type": "sops-age"}})
    called = {"n": 0}

    def boom(cfg=None):
        called["n"] += 1
        raise AssertionError("should not build remote when persist_to_vault is False")

    monkeypatch.setattr(core, "configured_remote_backend", boom)
    core.write_credential("KEY3", "v", ttl_hours=None, persist_to_vault=False)
    assert called["n"] == 0
    assert fake_backend["KEY3"] == "v"


def test_mirror_called_when_enabled_and_configured(isolated_dirs, fake_backend, monkeypatch):
    core.save_config({"remote_enabled": True, "remote_backend": {"type": "sops-age"}})

    puts = []

    class _SpyBackend(core.VaultBackend):
        name = "spy"
        supports_read = False

        def put(self, name, value, ttl_hours=None, persist_to_vault=False):
            puts.append((name, value))

        def get(self, name):
            return None

        def delete(self, name):
            return False

        def list(self):
            return []

    monkeypatch.setattr(core, "configured_remote_backend", lambda cfg=None: _SpyBackend())
    tag = core.write_credential("KEY4", "secret", ttl_hours=None, persist_to_vault=True)
    assert tag == "fake"  # local backend tag from the fake store
    assert puts == [("KEY4", "secret")]


def test_remote_failure_does_not_break_local(isolated_dirs, fake_backend, monkeypatch, capsys):
    core.save_config({"remote_enabled": True, "remote_backend": {"type": "sops-age"}})

    class _FailingBackend(core.VaultBackend):
        name = "failing"
        supports_read = False

        def put(self, name, value, ttl_hours=None, persist_to_vault=False):
            raise RuntimeError("remote unreachable")

        def get(self, name):
            return None

        def delete(self, name):
            return False

        def list(self):
            return []

    monkeypatch.setattr(core, "configured_remote_backend", lambda cfg=None: _FailingBackend())

    # Must NOT raise — local write has to survive a broken remote.
    tag = core.write_credential("KEY5", "v", ttl_hours=None, persist_to_vault=True)
    assert tag == "fake"
    # Local value intact + readable.
    value, _meta = core.read_credential("KEY5")
    assert value == "v"
    # Failure surfaced only as a warning on stderr.
    err = capsys.readouterr().err
    assert "remote mirror failed" in err


def test_remote_config_error_is_swallowed(isolated_dirs, fake_backend, monkeypatch, capsys):
    core.save_config({"remote_enabled": True, "remote_backend": {"type": "sops-age"}})

    def boom(cfg=None):
        raise ValueError("bad config")

    monkeypatch.setattr(core, "configured_remote_backend", boom)
    tag = core.write_credential("KEY6", "v", ttl_hours=None, persist_to_vault=True)
    assert tag == "fake"
    assert fake_backend["KEY6"] == "v"
    assert "config error" in capsys.readouterr().err
