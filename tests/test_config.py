"""Config layer + vault detection tests."""

from __future__ import annotations

import secret_paste_core as core


def test_load_config_defaults_when_missing(isolated_dirs):
    cfg = core.load_config()
    assert cfg["remote_enabled"] is False
    assert cfg["remote_backend"] is None


def test_save_then_load_roundtrip(isolated_dirs):
    core.save_config({"remote_enabled": True, "remote_backend": {"type": "sops-age"}})
    cfg = core.load_config()
    assert cfg["remote_enabled"] is True
    assert cfg["remote_backend"] == {"type": "sops-age"}


def test_load_config_corrupt_file_falls_back_to_defaults(isolated_dirs):
    core.config_path().write_text("{ this is : not json", encoding="utf-8")
    cfg = core.load_config()
    assert cfg == core.CONFIG_DEFAULTS


def test_load_config_non_dict_json_falls_back(isolated_dirs):
    core.config_path().write_text("[1, 2, 3]", encoding="utf-8")
    cfg = core.load_config()
    assert cfg == core.CONFIG_DEFAULTS


def test_load_config_unknown_keys_ignored(isolated_dirs):
    import json

    core.config_path().write_text(
        json.dumps({"remote_enabled": True, "evil": "drop-me"}), encoding="utf-8"
    )
    cfg = core.load_config()
    assert cfg["remote_enabled"] is True
    assert "evil" not in cfg


def test_save_config_drops_unknown_keys(isolated_dirs):
    import json

    core.save_config({"remote_enabled": True, "remote_backend": None, "junk": 1})
    on_disk = json.loads(core.config_path().read_text(encoding="utf-8"))
    assert "junk" not in on_disk
    assert set(on_disk) == set(core.CONFIG_DEFAULTS)


def test_set_remote_enabled_persists(isolated_dirs):
    core.set_remote_enabled(True)
    assert core.load_config()["remote_enabled"] is True
    core.set_remote_enabled(False)
    assert core.load_config()["remote_enabled"] is False


def test_detect_vaults_uses_path(monkeypatch):
    present = {"age", "op"}
    monkeypatch.setattr(
        core.shutil, "which", lambda name: f"/usr/bin/{name}" if name in present else None
    )
    detected = core.detect_vaults()
    assert set(detected) == present
    # Order follows KNOWN_VAULT_CLIS, not the set.
    assert detected == [n for n in core.KNOWN_VAULT_CLIS if n in present]


def test_detect_vaults_empty_when_none_present(monkeypatch):
    monkeypatch.setattr(core.shutil, "which", lambda _name: None)
    assert core.detect_vaults() == []
