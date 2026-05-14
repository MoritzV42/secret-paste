"""DPAPI roundtrip test with mocked pywin32.

These tests run on all platforms — they verify the wiring around
``_dpapi_encrypt`` / ``_dpapi_decrypt`` without requiring a real Windows
DPAPI host.
"""

from __future__ import annotations

import sys
import types

import pytest

import secret_paste_core as core


@pytest.fixture
def mocked_dpapi(monkeypatch):
    """Mock win32crypt.CryptProtectData / CryptUnprotectData."""
    state: dict[bytes, bytes] = {}

    def crypt_protect(data, desc, *_):
        # Return reversible "encryption" so the test can assert roundtrip.
        blob = b"DPAPI:" + data
        state[blob] = data
        return blob

    def crypt_unprotect(blob, *_):
        if blob not in state:
            # Fall back to "decrypt" by stripping marker
            assert blob.startswith(b"DPAPI:")
            return ("desc", blob[len(b"DPAPI:") :])
        return ("desc", state[blob])

    fake_module = types.SimpleNamespace(
        CryptProtectData=crypt_protect,
        CryptUnprotectData=crypt_unprotect,
    )
    monkeypatch.setattr(core, "win32crypt", fake_module, raising=False)
    monkeypatch.setattr(core, "HAS_DPAPI", True)
    monkeypatch.setattr(sys, "platform", "win32")
    return state


def test_dpapi_encrypt_decrypt_roundtrip(mocked_dpapi):
    blob = core._dpapi_encrypt("hello-world")
    assert blob.startswith(b"DPAPI:")
    out = core._dpapi_decrypt(blob)
    assert out == "hello-world"


def test_dpapi_full_write_read(monkeypatch, isolated_dirs, mocked_dpapi):
    # Don't mock _store/_load/_delete this time — exercise real DPAPI path.
    core.write_credential("API_KEY", "sk-live-42", ttl_hours=1, persist_to_vault=False)
    value, meta = core.read_credential("API_KEY")
    assert value == "sk-live-42"
    assert meta["backend"] == "dpapi"

    # On-disk blob exists and is the DPAPI-marked form.
    enc = core.enc_path("API_KEY").read_bytes()
    assert enc.startswith(b"DPAPI:")
    assert b"sk-live-42" in enc  # mocked DPAPI is reversible


def test_dpapi_missing_raises(monkeypatch):
    monkeypatch.setattr(core, "HAS_DPAPI", False)
    with pytest.raises(RuntimeError, match="pywin32"):
        core._dpapi_encrypt("x")
    with pytest.raises(RuntimeError, match="pywin32"):
        core._dpapi_decrypt(b"DPAPI:x")
