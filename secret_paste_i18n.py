"""Lightweight i18n for the secret-paste GUI dialog.

The dialog ships English by default (OSS adoption). DACH users can switch to a
German UI via a DE/EN toggle in the dialog or the ``--lang`` CLI flag. Only the
*GUI* is translated — CLI log output stays English on purpose (technical logs are
easier to grep / paste into issues regardless of UI language; see README).

Translations live as JSON files in ``locales/<code>.json``. Adding a language is
a pure data change: drop a new ``locales/<code>.json`` (copy ``en.json``, fill in
your strings) — no code edit needed. Missing keys fall back to English *per key*,
so a partial translation never shows blank labels.
"""

from __future__ import annotations

import json
import locale as _locale
from pathlib import Path

# Languages that ship with the package. The loader can still read any
# ``locales/<code>.json`` present on disk, but these are the ones the UI toggle
# and ``--lang`` officially advertise.
SUPPORTED_LANGS: tuple[str, ...] = ("en", "de")
DEFAULT_LANG = "en"

# Embedded English baseline. The shipped ``locales/en.json`` is the source of
# truth and overrides this at runtime, but keeping a copy in code means the tool
# *always* renders complete English labels even if the JSON files are missing
# from an install (e.g. a packaging gap) — no blank dialog, ever.
_EN_FALLBACK: dict[str, str] = {
    "header": "Enter credential: {key}",
    "paste_hint": (
        "Paste the value (Ctrl+V on Win/Linux, ⌘V on macOS). "
        "Stored locally on this machine."
    ),
    "paste_button": "Paste",
    "show_value": "Show value",
    "mirror_remote": "Also mirror to remote backend",
    "detected_vaults": "Detected: {vaults}. See ROADMAP.md.",
    "store_permanently": "Store permanently (no local TTL)",
    "backend": "Backend: {label}",
    "save": "Save",
    "cancel": "Cancel",
    "error_empty": "Please enter a value.",
    "toast_stored": "[OK] Stored: {key}",
}

# Module-level cache so we do not re-read the JSON on every retranslate() call.
_CACHE: dict[str, dict] = {}


def locales_dir() -> Path:
    """Directory holding the ``<code>.json`` translation files (next to this module)."""
    return Path(__file__).resolve().parent / "locales"


def _read_locale_file(lang: str) -> dict:
    """Read one ``locales/<lang>.json`` file. Returns ``{}`` if absent/corrupt."""
    if lang in _CACHE:
        return _CACHE[lang]
    path = locales_dir() / f"{lang}.json"
    data: dict = {}
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data = {str(k): str(v) for k, v in loaded.items()}
        except Exception:  # noqa: BLE001 — corrupt JSON must never crash the dialog
            data = {}
    _CACHE[lang] = data
    return data


def load_locale(lang: str | None) -> dict:
    """Return the string map for ``lang`` with per-key fallback to English.

    The returned dict always contains every English key. Any key missing from the
    requested language (or an entirely unknown language) falls back to the English
    string for that key — so a half-finished translation never yields blanks.

    ``lang=None`` or an unknown language resolves to English.
    """
    # Start from the embedded EN baseline so every key is always present, then
    # let the shipped en.json override (it is the source of truth on disk).
    base = dict(_EN_FALLBACK)
    base.update(_read_locale_file(DEFAULT_LANG))
    norm = normalize_lang(lang)
    if norm == DEFAULT_LANG:
        return base
    overlay = _read_locale_file(norm)
    # Per-key overlay: keep the EN fallback for every key the overlay omits.
    for key, value in overlay.items():
        base[key] = value
    return base


def normalize_lang(lang: str | None) -> str:
    """Map an arbitrary language hint to a supported code, defaulting to English.

    Accepts forms like ``"de"``, ``"DE"``, ``"de_DE"``, ``"de-AT"`` → ``"de"``.
    Anything not in SUPPORTED_LANGS (or ``None``) → ``DEFAULT_LANG``.
    """
    if not lang:
        return DEFAULT_LANG
    code = str(lang).strip().lower().replace("-", "_").split("_", 1)[0]
    return code if code in SUPPORTED_LANGS else DEFAULT_LANG


def system_default_lang() -> str:
    """Best-effort first-run default from the OS locale.

    German system locale (``de_*``) → ``"de"``; everything else → ``"en"``.
    ``locale.getdefaultlocale()`` can return ``(None, None)`` on some systems —
    that is guarded, falling back to English.
    """
    try:
        code = _locale.getdefaultlocale()[0]  # e.g. "de_DE", "en_US", or None
    except Exception:  # noqa: BLE001 — some platforms raise instead of returning None
        code = None
    if not code:
        return DEFAULT_LANG
    return "de" if code.lower().startswith("de") else DEFAULT_LANG


class Translator:
    """Holds the active language + string map and formats keys on demand.

    The dialog keeps one Translator and calls ``set_lang()`` when the toggle
    flips; widgets are re-translated by re-reading ``t(key, **fmt)``.
    """

    def __init__(self, lang: str | None = None):
        self.lang = normalize_lang(lang)
        self._strings = load_locale(self.lang)

    def set_lang(self, lang: str | None) -> str:
        """Switch language; returns the normalized code actually applied."""
        self.lang = normalize_lang(lang)
        self._strings = load_locale(self.lang)
        return self.lang

    def t(self, key_: str, **fmt) -> str:
        """Return the localized string for ``key_``, ``str.format``-ed with ``fmt``.

        The parameter is named ``key_`` (trailing underscore) so callers can pass
        a ``key=`` *format placeholder* (the dialog uses ``{key}`` in the header /
        toast strings) without colliding with the lookup argument.

        Unknown keys return the key itself (visible-but-harmless) instead of
        raising, so a typo never crashes the dialog. Missing format placeholders
        are tolerated — the raw string is returned unformatted.
        """
        template = self._strings.get(key_, key_)
        if not fmt:
            return template
        try:
            return template.format(**fmt)
        except Exception:  # noqa: BLE001 — bad/missing placeholder, show raw
            return template
