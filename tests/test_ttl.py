"""TTL / expiry logic and metadata roundtrip."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import secret_paste_core as core


def test_is_expired_when_ttl_none_returns_false():
    meta = {"created": datetime.now(timezone.utc).isoformat(), "ttl_hours": None}
    assert core.is_expired(meta) is False


def test_is_expired_when_in_window_returns_false():
    meta = {
        "created": datetime.now(timezone.utc).isoformat(),
        "ttl_hours": 24,
    }
    assert core.is_expired(meta) is False


def test_is_expired_when_past_ttl_returns_true():
    created = datetime.now(timezone.utc) - timedelta(hours=25)
    meta = {"created": created.isoformat(), "ttl_hours": 24}
    assert core.is_expired(meta) is True


def test_is_expired_with_bad_timestamp_returns_true():
    meta = {"created": "not-a-date", "ttl_hours": 24}
    assert core.is_expired(meta) is True


def test_expires_at_with_ttl_returns_future_dt():
    now = datetime.now(timezone.utc)
    meta = {"created": now.isoformat(), "ttl_hours": 6}
    exp = core.expires_at(meta)
    assert exp is not None
    assert abs((exp - (now + timedelta(hours=6))).total_seconds()) < 1


def test_expires_at_with_no_ttl_returns_none():
    meta = {"created": datetime.now(timezone.utc).isoformat(), "ttl_hours": None}
    assert core.expires_at(meta) is None


def test_write_then_read_credential_roundtrips_value_and_meta(isolated_dirs, fake_backend):
    core.write_credential("BREVO_KEY", "sk-test-123", ttl_hours=2, persist_to_vault=False)
    value, meta = core.read_credential("BREVO_KEY")
    assert value == "sk-test-123"
    assert meta is not None
    assert meta["name"] == "BREVO_KEY"
    assert meta["ttl_hours"] == 2
    assert meta["persist_to_vault"] is False
    assert meta["backend"] == "fake"
    assert fake_backend["BREVO_KEY"] == "sk-test-123"


def test_read_credential_returns_none_for_expired(isolated_dirs, fake_backend, monkeypatch):
    core.write_credential("X", "v", ttl_hours=1, persist_to_vault=False)
    # Rewrite meta with a stale timestamp.
    mp = core.meta_path("X")
    meta = mp.read_text(encoding="utf-8")
    import json

    parsed = json.loads(meta)
    parsed["created"] = (datetime.now(timezone.utc) - timedelta(hours=10)).isoformat()
    mp.write_text(json.dumps(parsed), encoding="utf-8")

    value, meta = core.read_credential("X")
    assert value is None
    assert meta is not None  # caller still gets the (stale) metadata snapshot
    # Opportunistic purge: the value must no longer be in the backend, and
    # the meta-file must be gone from disk.
    assert "X" not in fake_backend
    assert not mp.exists()


def test_read_credential_missing_returns_none_none(isolated_dirs, fake_backend):
    value, meta = core.read_credential("NOPE")
    assert value is None
    assert meta is None


def test_list_local_marks_expired(isolated_dirs, fake_backend):
    core.write_credential("FRESH", "v", ttl_hours=24, persist_to_vault=False)
    core.write_credential("OLD", "v", ttl_hours=1, persist_to_vault=False)

    # Backdate OLD
    import json

    mp = core.meta_path("OLD")
    parsed = json.loads(mp.read_text(encoding="utf-8"))
    parsed["created"] = (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat()
    mp.write_text(json.dumps(parsed), encoding="utf-8")

    entries = {m["name"]: m for m in core.list_local()}
    assert entries["FRESH"]["_expired"] is False
    assert entries["OLD"]["_expired"] is True


def test_delete_local_removes_value_and_meta(isolated_dirs, fake_backend):
    core.write_credential("Z", "v", ttl_hours=None, persist_to_vault=False)
    assert core.meta_path("Z").exists()
    assert fake_backend.get("Z") == "v"

    assert core.delete_local("Z") is True
    assert not core.meta_path("Z").exists()
    assert "Z" not in fake_backend


def test_delete_local_returns_false_when_missing(isolated_dirs, fake_backend):
    assert core.delete_local("NOTHING") is False
