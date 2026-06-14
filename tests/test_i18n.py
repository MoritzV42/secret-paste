"""Tests for the i18n locale loader (issue #3).

These exercise only the pure-Python loader / Translator and the config-locale
persistence. No real Tk dialog is ever instantiated.
"""

from __future__ import annotations

import json

import secret_paste_core as core
import secret_paste_i18n as i18n

# --- normalize_lang ------------------------------------------------------


def test_normalize_lang_variants():
    assert i18n.normalize_lang("de") == "de"
    assert i18n.normalize_lang("DE") == "de"
    assert i18n.normalize_lang("de_DE") == "de"
    assert i18n.normalize_lang("de-AT") == "de"
    assert i18n.normalize_lang("en") == "en"
    assert i18n.normalize_lang("en_US") == "en"


def test_normalize_lang_unknown_falls_back_to_en():
    assert i18n.normalize_lang("fr") == "en"
    assert i18n.normalize_lang("zz_ZZ") == "en"
    assert i18n.normalize_lang("") == "en"
    assert i18n.normalize_lang(None) == "en"


# --- load_locale: per-key EN fallback ------------------------------------


def test_load_locale_en_is_complete():
    en = i18n.load_locale("en")
    # Sanity: the localizable keys the dialog relies on must all be present.
    for key in (
        "header",
        "paste_hint",
        "paste_button",
        "show_value",
        "mirror_remote",
        "detected_vaults",
        "store_permanently",
        "backend",
        "save",
        "cancel",
        "error_empty",
        "toast_stored",
    ):
        assert key in en and en[key]


def test_load_locale_de_has_real_umlauts():
    de = i18n.load_locale("de")
    assert de["save"] == "Speichern"
    assert de["cancel"] == "Abbrechen"
    assert de["error_empty"] == "Bitte einen Wert eingeben."
    assert de["show_value"] == "Wert anzeigen"
    assert de["store_permanently"] == "Dauerhaft speichern (kein lokales TTL)"
    # Real umlauts, not ASCII replacements. "Einfügen" (ü), "Zusätzlich" (ä).
    assert de["paste_button"] == "Einfügen"
    assert "ü" in de["paste_button"]
    assert "ä" in de["mirror_remote"]
    assert "ü" in de["paste_hint"]


def test_load_locale_unknown_lang_returns_english(monkeypatch):
    # An unknown language must resolve to the full English map.
    assert i18n.load_locale("fr") == i18n.load_locale("en")


def test_load_locale_missing_key_falls_back_per_key(tmp_path, monkeypatch):
    """A partial translation must inherit EN for any key it omits."""
    fake = tmp_path / "locales"
    fake.mkdir()
    # Real EN baseline copied from the shipped file so all keys exist.
    en = i18n.load_locale("en")
    (fake / "en.json").write_text(json.dumps(en), encoding="utf-8")
    # Partial xx locale: only translate two keys.
    (fake / "xx.json").write_text(
        json.dumps({"save": "Sparen", "cancel": "Stornieren"}), encoding="utf-8"
    )
    monkeypatch.setattr(i18n, "locales_dir", lambda: fake)
    i18n._CACHE.clear()
    monkeypatch.setattr(i18n, "SUPPORTED_LANGS", ("en", "xx"))

    merged = i18n.load_locale("xx")
    # Translated keys win...
    assert merged["save"] == "Sparen"
    assert merged["cancel"] == "Stornieren"
    # ...missing keys fall back to EN, never blank.
    assert merged["header"] == en["header"]
    assert merged["store_permanently"] == en["store_permanently"]
    assert set(merged) == set(en)
    i18n._CACHE.clear()


# --- system_default_lang -------------------------------------------------


def test_system_default_lang_german(monkeypatch):
    monkeypatch.setattr(i18n._locale, "getdefaultlocale", lambda: ("de_DE", "UTF-8"))
    assert i18n.system_default_lang() == "de"


def test_system_default_lang_non_german(monkeypatch):
    monkeypatch.setattr(i18n._locale, "getdefaultlocale", lambda: ("en_US", "UTF-8"))
    assert i18n.system_default_lang() == "en"


def test_system_default_lang_handles_none(monkeypatch):
    # getdefaultlocale() may return (None, None) — must not crash, defaults EN.
    monkeypatch.setattr(i18n._locale, "getdefaultlocale", lambda: (None, None))
    assert i18n.system_default_lang() == "en"


def test_system_default_lang_handles_exception(monkeypatch):
    def boom():
        raise ValueError("unknown locale")

    monkeypatch.setattr(i18n._locale, "getdefaultlocale", boom)
    assert i18n.system_default_lang() == "en"


# --- Translator ----------------------------------------------------------


def test_translator_formats_placeholders():
    tr = i18n.Translator("en")
    assert tr.t("header", key="BREVO_KEY") == "Enter credential: BREVO_KEY"
    assert tr.t("toast_stored", key="X") == "[OK] Stored: X"


def test_translator_set_lang_switches_strings():
    tr = i18n.Translator("en")
    assert tr.t("save") == "Save"
    applied = tr.set_lang("de")
    assert applied == "de"
    assert tr.t("save") == "Speichern"
    # Switching back works too.
    tr.set_lang("en")
    assert tr.t("save") == "Save"


def test_translator_unknown_key_returns_key():
    tr = i18n.Translator("en")
    assert tr.t("does_not_exist") == "does_not_exist"


def test_translator_unknown_lang_defaults_english():
    tr = i18n.Translator("fr")
    assert tr.lang == "en"
    assert tr.t("save") == "Save"


# --- config-locale persistence ------------------------------------------


def test_set_locale_persists(isolated_dirs):
    assert core.load_config()["locale"] is None  # auto by default
    core.set_locale("de")
    assert core.load_config()["locale"] == "de"
    core.set_locale("en")
    assert core.load_config()["locale"] == "en"
    # Clearing back to auto.
    core.set_locale(None)
    assert core.load_config()["locale"] is None


def test_locale_in_config_defaults(isolated_dirs):
    assert "locale" in core.CONFIG_DEFAULTS
    assert core.CONFIG_DEFAULTS["locale"] is None
