"""Temp-file write + TTL cleanup."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import secret_paste_core as core


def test_write_tmp_value_creates_value_and_marker(isolated_dirs, fake_backend):
    p = core.write_tmp_value("FOO", "secret-value")
    assert p.exists()
    assert p.read_text(encoding="utf-8") == "secret-value"
    marker = p.with_suffix(".val.expires")
    assert marker.exists()
    # Marker contains a future ISO timestamp
    exp = datetime.fromisoformat(marker.read_text(encoding="utf-8").strip())
    assert exp > datetime.now(timezone.utc)


def test_cleanup_tmp_removes_expired(isolated_dirs, fake_backend):
    p = core.write_tmp_value("EXP", "x")
    marker = p.with_suffix(".val.expires")
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    marker.write_text(past.isoformat(), encoding="utf-8")

    core.cleanup_tmp()
    assert not p.exists()
    assert not marker.exists()


def test_cleanup_tmp_keeps_fresh(isolated_dirs, fake_backend):
    p = core.write_tmp_value("FRESH", "x")
    marker = p.with_suffix(".val.expires")
    core.cleanup_tmp()
    assert p.exists()
    assert marker.exists()


def test_write_tmp_triggers_cleanup_of_others(isolated_dirs, fake_backend):
    # Old file
    old = core.write_tmp_value("OLD", "x")
    old_marker = old.with_suffix(".val.expires")
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    old_marker.write_text(past.isoformat(), encoding="utf-8")

    # Writing a new value should clean up the old one
    core.write_tmp_value("NEW", "y")
    assert not old.exists()


def test_cleanup_ignores_unparseable_marker(isolated_dirs, fake_backend):
    p = core.write_tmp_value("OK", "x")
    marker = p.with_suffix(".val.expires")
    marker.write_text("not-iso", encoding="utf-8")
    # Should not raise; just skip
    core.cleanup_tmp()


def test_ttl_remaining_fresh_value_in_window(isolated_dirs, fake_backend):
    core.write_tmp_value("R1", "x")
    remaining = core.tmp_ttl_remaining("R1")
    assert remaining is not None
    assert 0 < remaining <= core.TMP_TTL_MINUTES * 60


def test_ttl_remaining_expired_clamps_to_zero(isolated_dirs, fake_backend):
    p = core.write_tmp_value("R2", "x")
    marker = p.with_suffix(".val.expires")
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    marker.write_text(past.isoformat(), encoding="utf-8")
    assert core.tmp_ttl_remaining("R2") == 0


def test_ttl_remaining_no_marker_returns_none(isolated_dirs, fake_backend):
    assert core.tmp_ttl_remaining("NEVER_WRITTEN") is None


def test_ttl_remaining_unparseable_marker_returns_none(isolated_dirs, fake_backend):
    p = core.write_tmp_value("R3", "x")
    marker = p.with_suffix(".val.expires")
    marker.write_text("garbage", encoding="utf-8")
    assert core.tmp_ttl_remaining("R3") is None
