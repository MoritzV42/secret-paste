"""Shared helpers for secret-paste tools.

Currently stdlib + pywin32 (DPAPI on Windows). No third-party PyPI
dependencies for the core local backend.

This module also defines the ``VaultBackend`` plugin interface. The current
release ships only ``LocalDPAPIBackend`` (Windows). Future backends
(Bitwarden, 1Password, SSH-vault, macOS Keychain, Linux libsecret) plug into
the same interface â€” see ``ROADMAP.md``.
"""
from __future__ import annotations

import json
import os
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Tuple

# DPAPI via pywin32 (Windows only)
try:
    import win32crypt  # type: ignore
    HAS_DPAPI = True
except ImportError:
    HAS_DPAPI = False


# --- Paths ---------------------------------------------------------------

def store_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~\\AppData\\Local")
    p = Path(base) / "secret-paste"
    p.mkdir(parents=True, exist_ok=True)
    return p


def tmp_dir() -> Path:
    base = os.environ.get("TEMP") or os.path.expanduser("~\\AppData\\Local\\Temp")
    p = Path(base) / "secret-paste-tmp"
    p.mkdir(parents=True, exist_ok=True)
    return p


def enc_path(name: str) -> Path:
    return store_dir() / f"{_safe_name(name)}.enc"


def meta_path(name: str) -> Path:
    return store_dir() / f"{_safe_name(name)}.meta.json"


def tmp_val_path(name: str) -> Path:
    return tmp_dir() / f"{_safe_name(name)}.val"


def _safe_name(name: str) -> str:
    # Prevent path traversal. Allows only [A-Za-z0-9_.-]
    cleaned = "".join(c for c in name if c.isalnum() or c in ("_", "-", "."))
    if not cleaned:
        raise ValueError("Invalid key name (empty after sanitizing).")
    return cleaned


# --- DPAPI ---------------------------------------------------------------

def dpapi_encrypt(plaintext: str) -> bytes:
    if not HAS_DPAPI:
        raise RuntimeError(
            "pywin32 not installed. Please run: pip install pywin32"
        )
    blob = win32crypt.CryptProtectData(
        plaintext.encode("utf-8"),
        "secret-paste",  # description
        None, None, None, 0,
    )
    return blob


def dpapi_decrypt(blob: bytes) -> str:
    if not HAS_DPAPI:
        raise RuntimeError(
            "pywin32 not installed. Please run: pip install pywin32"
        )
    _desc, data = win32crypt.CryptUnprotectData(blob, None, None, None, 0)
    return data.decode("utf-8")


# --- Meta ----------------------------------------------------------------

def write_credential(name: str, value: str, ttl_hours: Optional[int],
                     persist_to_vault: bool) -> None:
    blob = dpapi_encrypt(value)
    enc_path(name).write_bytes(blob)
    now = datetime.now(timezone.utc)
    meta = {
        "name": _safe_name(name),
        "created": now.isoformat(),
        "ttl_hours": ttl_hours,  # None = unlimited
        "persist_to_vault": bool(persist_to_vault),
    }
    meta_path(name).write_text(json.dumps(meta, indent=2), encoding="utf-8")


def read_meta(name: str) -> Optional[dict]:
    mp = meta_path(name)
    if not mp.exists():
        return None
    try:
        return json.loads(mp.read_text(encoding="utf-8"))
    except Exception:
        return None


def is_expired(meta: dict) -> bool:
    ttl = meta.get("ttl_hours")
    if ttl is None:
        return False
    try:
        created = datetime.fromisoformat(meta["created"])
    except Exception:
        return True
    expires = created + timedelta(hours=int(ttl))
    return datetime.now(timezone.utc) >= expires


def expires_at(meta: dict) -> Optional[datetime]:
    ttl = meta.get("ttl_hours")
    if ttl is None:
        return None
    try:
        created = datetime.fromisoformat(meta["created"])
    except Exception:
        return None
    return created + timedelta(hours=int(ttl))


def list_local() -> list[dict]:
    items = []
    for mp in sorted(store_dir().glob("*.meta.json")):
        try:
            meta = json.loads(mp.read_text(encoding="utf-8"))
            meta["_expired"] = is_expired(meta)
            items.append(meta)
        except Exception:
            continue
    return items


def delete_local(name: str) -> bool:
    deleted = False
    for p in (enc_path(name), meta_path(name), tmp_val_path(name)):
        if p.exists():
            try:
                p.unlink()
                deleted = True
            except OSError:
                pass
    return deleted


def read_credential(name: str) -> Tuple[Optional[str], Optional[dict]]:
    meta = read_meta(name)
    if meta is None:
        return None, None
    if is_expired(meta):
        return None, meta
    ep = enc_path(name)
    if not ep.exists():
        return None, meta
    try:
        value = dpapi_decrypt(ep.read_bytes())
        return value, meta
    except Exception as exc:
        print(f"WARN: DPAPI decryption failed: {exc}",
              file=sys.stderr)
        return None, meta


# --- Tmp file with TTL ---------------------------------------------------

TMP_TTL_MINUTES = 5


def write_tmp_value(name: str, value: str) -> Path:
    """Write value to temp file. Also triggers cleanup of expired temp files."""
    cleanup_tmp()
    p = tmp_val_path(name)
    # File with restricted permissions (best effort on Windows)
    p.write_text(value, encoding="utf-8", newline="")
    # TTL marker
    marker = p.with_suffix(".val.expires")
    expires = datetime.now(timezone.utc) + timedelta(minutes=TMP_TTL_MINUTES)
    marker.write_text(expires.isoformat(), encoding="utf-8")
    return p


def cleanup_tmp() -> None:
    now = datetime.now(timezone.utc)
    for marker in tmp_dir().glob("*.val.expires"):
        try:
            exp = datetime.fromisoformat(marker.read_text(encoding="utf-8").strip())
            if now >= exp:
                val_file = marker.with_suffix("")  # remove ".expires" -> .val
                if val_file.exists():
                    val_file.unlink()
                marker.unlink()
        except Exception:
            continue


# --- Format helpers ------------------------------------------------------

def fmt_local(dt: datetime) -> str:
    return dt.astimezone().strftime("%Y-%m-%d %H:%M")


# --- Vault Plugin Interface ----------------------------------------------

@dataclass
class CredMeta:
    """Metadata for a credential entry (never carries the value itself)."""
    name: str
    created_at: Optional[str] = None
    expires_at: Optional[str] = None
    persist_to_vault: bool = False
    source: str = "local"  # "local" | "vault" | backend-specific id
    extra: dict = field(default_factory=dict)


class VaultBackend(ABC):
    """Pluggable backend for credential storage.

    Implementations must NEVER print or log credential values. ``get`` is the
    only method allowed to return the plaintext value, and only to the caller.
    """

    name: str = "abstract"

    @abstractmethod
    def put(self, name: str, value: str) -> None:
        """Store ``value`` under ``name``. Overwrites existing entries."""

    @abstractmethod
    def get(self, name: str) -> Optional[str]:
        """Return plaintext value or ``None`` if missing/expired."""

    @abstractmethod
    def delete(self, name: str) -> bool:
        """Delete the entry. Returns True if something was deleted."""

    @abstractmethod
    def list(self) -> list[CredMeta]:
        """Return metadata for all entries. Never returns values."""


class LocalDPAPIBackend(VaultBackend):
    """Default backend on Windows: per-user DPAPI-encrypted blob on disk."""

    name = "local-dpapi"

    def put(self, name: str, value: str) -> None:
        # ttl/persist are handled by the CLI layer (see write_credential).
        # This shortcut creates a permanent entry; secret-paste.py uses
        # ``write_credential`` directly for TTL/persist semantics.
        write_credential(name, value, ttl_hours=None, persist_to_vault=False)

    def get(self, name: str) -> Optional[str]:
        value, _meta = read_credential(name)
        return value

    def delete(self, name: str) -> bool:
        return delete_local(name)

    def list(self) -> list[CredMeta]:
        out: list[CredMeta] = []
        for m in list_local():
            exp = expires_at(m)
            out.append(CredMeta(
                name=m["name"],
                created_at=m.get("created"),
                expires_at=exp.isoformat() if exp else None,
                persist_to_vault=bool(m.get("persist_to_vault")),
                source="local",
                extra={"_expired": bool(m.get("_expired"))},
            ))
        return out


# Stubs for future backends â€” see ROADMAP.md:
#
# class RemoteSSHBackend(VaultBackend):
#     """Mirror credentials to a remote SQLite vault via SSH + Fernet."""
#     name = "remote-ssh"
#     ...
#
# class BitwardenBackend(VaultBackend):
#     """Fetch/store via Bitwarden CLI (`bw`)."""
#     name = "bitwarden"
#     ...
#
# class OnePasswordBackend(VaultBackend):
#     """Fetch/store via 1Password CLI (`op`)."""
#     name = "1password"
#     ...
#
# class KeyringBackend(VaultBackend):
#     """Cross-platform via the `keyring` library (macOS Keychain, libsecret)."""
#     name = "keyring"
#     ...


def default_backend() -> VaultBackend:
    """Return the default backend for the current platform."""
    if sys.platform == "win32" and HAS_DPAPI:
        return LocalDPAPIBackend()
    raise RuntimeError(
        "secret-paste is currently Windows-only. "
        "Linux/Mac via keyring planned â€” see ROADMAP.md."
    )
