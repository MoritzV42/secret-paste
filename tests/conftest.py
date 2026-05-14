"""Shared fixtures for the test suite.

Every test gets:

* An isolated ``store_dir`` and ``tmp_dir`` (no leakage to the real user
  profile).
* A patched value backend (``_store_value``/``_load_value``/``_delete_value``)
  that uses an in-process dict — so tests run on every OS regardless of
  whether pywin32 or keyring is installed.
"""

from __future__ import annotations

import os
import sys

import pytest

# Ensure the project root is on sys.path so `import secret_paste_core` works
# when running ``pytest`` from the repo root in editable-but-not-installed mode.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


@pytest.fixture
def isolated_dirs(tmp_path, monkeypatch):
    """Redirect store_dir() and tmp_dir() into ``tmp_path``."""
    import secret_paste_core as core

    store = tmp_path / "store"
    temp = tmp_path / "tmp"
    store.mkdir()
    temp.mkdir()
    monkeypatch.setattr(core, "store_dir", lambda: store)
    monkeypatch.setattr(core, "tmp_dir", lambda: temp)
    return store, temp


@pytest.fixture
def fake_backend(monkeypatch):
    """In-process key/value store replacing DPAPI/keyring."""
    import secret_paste_core as core

    store: dict[str, str] = {}

    def fake_store(name: str, value: str) -> str:
        store[core._safe_name(name)] = value
        return "fake"

    def fake_load(name: str):
        return store.get(core._safe_name(name))

    def fake_delete(name: str):
        safe = core._safe_name(name)
        if safe in store:
            del store[safe]
        return True, None  # absent or removed — both fine

    monkeypatch.setattr(core, "_store_value", fake_store)
    monkeypatch.setattr(core, "_load_value", fake_load)
    monkeypatch.setattr(core, "_delete_value", fake_delete)
    return store
