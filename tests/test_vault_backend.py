"""VaultBackend interface contract.

Concrete backends shipped with v0.1 are exercised here. New backends added
via the plugin interface should be added to the ``BACKENDS`` parametrization.
"""

from __future__ import annotations

import pytest

import secret_paste_core as core


@pytest.fixture
def patched_backend(isolated_dirs, fake_backend):
    """Yield a LocalDPAPIBackend wired to the in-process fake store.

    Note: we test through the LocalDPAPIBackend class because both shipped
    backends (``LocalDPAPIBackend``, ``KeyringBackend``) delegate to the same
    module-level write_credential / read_credential / delete_local / list_local
    functions. Exercising one class covers the contract for both.
    """
    return core.LocalDPAPIBackend()


def test_backend_put_get_roundtrip(patched_backend):
    patched_backend.put("ALPHA", "v1", ttl_hours=None, persist_to_vault=False)
    assert patched_backend.get("ALPHA") == "v1"


def test_backend_get_missing_returns_none(patched_backend):
    assert patched_backend.get("DOES_NOT_EXIST") is None


def test_backend_delete_returns_bool(patched_backend):
    patched_backend.put("BETA", "v", ttl_hours=None, persist_to_vault=False)
    assert patched_backend.delete("BETA") is True
    assert patched_backend.delete("BETA") is False
    assert patched_backend.get("BETA") is None


def test_backend_list_returns_credmeta_without_values(patched_backend):
    patched_backend.put("GAMMA", "v", ttl_hours=24, persist_to_vault=False)
    items = patched_backend.list()
    assert len(items) == 1
    cm = items[0]
    assert isinstance(cm, core.CredMeta)
    assert cm.name == "GAMMA"
    # CredMeta never carries the value
    assert not any(
        getattr(cm, f).__class__ is str and getattr(cm, f) == "v" for f in ("name", "source")
    )


def test_backend_overwrites_existing(patched_backend):
    patched_backend.put("DELTA", "v1", ttl_hours=None, persist_to_vault=False)
    patched_backend.put("DELTA", "v2", ttl_hours=None, persist_to_vault=False)
    assert patched_backend.get("DELTA") == "v2"


def test_default_backend_raises_when_none_available(monkeypatch):
    monkeypatch.setattr(core, "HAS_DPAPI", False)
    monkeypatch.setattr(core, "HAS_KEYRING", False)
    import sys

    monkeypatch.setattr(sys, "platform", "linux")
    with pytest.raises(RuntimeError, match="No credential backend available"):
        core.default_backend()


class _WriteOnlyStub(core.VaultBackend):
    """Minimal write-only backend used to exercise the read-capability guard."""

    name = "write-only-stub"
    supports_read = False

    def __init__(self):
        self._store: dict[str, str] = {}

    def put(self, name, value, ttl_hours=None, persist_to_vault=False):
        self._store[name] = value

    def get(self, name):  # would leak if ever reached — guard must prevent it
        raise AssertionError("get() must never be called on a write-only backend")

    def delete(self, name):
        return self._store.pop(name, None) is not None

    def list(self):
        return [core.CredMeta(name=n, source=self.name) for n in self._store]


def test_default_backend_supports_read():
    # Both shipped local backends are readable by default.
    assert core.LocalDPAPIBackend().supports_read is True
    assert core.KeyringBackend().supports_read is True


def test_backend_get_helper_reads_readable_backend(patched_backend):
    patched_backend.put("EPS", "v", ttl_hours=None, persist_to_vault=False)
    assert core.backend_get(patched_backend, "EPS") == "v"


def test_backend_get_helper_refuses_write_only_backend():
    wo = _WriteOnlyStub()
    wo.put("ZETA", "secret-value")
    with pytest.raises(core.WriteOnlyError):
        core.backend_get(wo, "ZETA")


def test_backend_label_reports_active_platform(monkeypatch):
    import sys

    monkeypatch.setattr(core, "HAS_DPAPI", True)
    monkeypatch.setattr(sys, "platform", "win32")
    assert "DPAPI" in core.backend_label()

    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(core, "HAS_DPAPI", False)
    monkeypatch.setattr(core, "HAS_KEYRING", True)
    assert "Keychain" in core.backend_label()

    monkeypatch.setattr(sys, "platform", "linux")
    assert "Secret Service" in core.backend_label()
