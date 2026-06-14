"""Shared helpers for the secret-paste CLI tools.

Cross-platform secret storage:

* Windows: per-user DPAPI-encrypted blob on disk (``pywin32``).
* macOS / Linux: ``keyring`` library (Keychain / libsecret / kwallet / etc.).
* Anywhere: metadata JSON on disk next to the value.

This module also defines the ``VaultBackend`` plugin interface. Future
backends (Bitwarden, 1Password, sops/age) plug into the same interface — see
``ROADMAP.md``.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

# DPAPI via pywin32 (Windows only)
try:
    import win32crypt  # type: ignore

    HAS_DPAPI = True
except ImportError:
    HAS_DPAPI = False

# keyring (macOS Keychain, Linux libsecret/kwallet/...)
try:
    import keyring  # type: ignore
    import keyring.errors  # type: ignore

    HAS_KEYRING = True
except ImportError:
    HAS_KEYRING = False

KEYRING_SERVICE = "secret-paste"

# Windows reserved device names (cannot be used as filenames).
_WIN_RESERVED = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


# --- Paths ---------------------------------------------------------------


def store_dir() -> Path:
    """Per-user data directory for metadata + DPAPI blobs."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~\\AppData\\Local")
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    p = Path(base) / "secret-paste"
    p.mkdir(parents=True, exist_ok=True)
    if os.name == "posix":
        try:
            os.chmod(p, 0o700)
        except OSError:
            pass
    return p


def tmp_dir() -> Path:
    """Per-user temp directory for the 5-minute-TTL value drops.

    On POSIX, the directory is suffixed with the user's UID so a second user
    on the same host gets their own dir (``/tmp`` is world-readable on most
    Linux distros). Mode is forced to ``0700``.
    """
    if os.name == "posix":
        uid = os.getuid()  # noqa: SIM115
        # XDG_RUNTIME_DIR is the canonical "user-scoped runtime dir" on Linux.
        base = os.environ.get("XDG_RUNTIME_DIR") or tempfile.gettempdir()
        p = Path(base) / f"secret-paste-tmp-{uid}"
    else:
        p = Path(tempfile.gettempdir()) / "secret-paste-tmp"
    p.mkdir(parents=True, exist_ok=True)
    if os.name == "posix":
        try:
            os.chmod(p, 0o700)
        except OSError:
            pass
    return p


def enc_path(name: str) -> Path:
    return store_dir() / f"{_safe_name(name)}.enc"


def meta_path(name: str) -> Path:
    return store_dir() / f"{_safe_name(name)}.meta.json"


def tmp_val_path(name: str) -> Path:
    return tmp_dir() / f"{_safe_name(name)}.val"


def _safe_name(name: str) -> str:
    """Sanitize a key name to ``[A-Za-z0-9_.-]+``.

    Raises ``ValueError`` if:
      * the result is empty,
      * the result has no alphanumeric character (e.g. ``..\\..\\`` → ``....``),
      * the result starts with ``.`` (Unix-hidden, also messes with our
        ``<name>.meta.json`` convention), or
      * the result is a Windows reserved device name (CON, PRN, AUX, NUL,
        COM1–COM9, LPT1–LPT9), which fail to create as files on Windows.
    """
    cleaned = "".join(c for c in name if c.isalnum() or c in ("_", "-", "."))
    if not cleaned:
        raise ValueError("Invalid key name (empty after sanitizing).")
    if not any(c.isalnum() for c in cleaned):
        raise ValueError("Invalid key name (must contain at least one letter or digit).")
    if cleaned.startswith("."):
        raise ValueError("Invalid key name (must not start with '.').")
    stem = cleaned.split(".", 1)[0].upper()
    if stem in _WIN_RESERVED:
        raise ValueError(f"Invalid key name ({cleaned!r} is a Windows reserved device name).")
    return cleaned


# --- Config layer --------------------------------------------------------

# Default config: remote mirroring is OFF until the user opts in. A None
# backend means "no remote backend configured yet" even when remote_enabled.
CONFIG_DEFAULTS: dict = {
    "remote_enabled": False,
    "remote_backend": None,
}


def config_path() -> Path:
    return store_dir() / "config.json"


def load_config() -> dict:
    """Load config, merged over defaults. Robust against a missing/corrupt file.

    A missing or unparseable ``config.json`` yields a copy of CONFIG_DEFAULTS
    instead of raising — the tool must keep working with safe defaults even if
    the file was hand-edited into invalid JSON.
    """
    cfg = dict(CONFIG_DEFAULTS)
    cp = config_path()
    if not cp.exists():
        return cfg
    try:
        data = json.loads(cp.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — corrupt JSON, unreadable file, etc.
        return cfg
    if isinstance(data, dict):
        cfg.update({k: data[k] for k in CONFIG_DEFAULTS if k in data})
    return cfg


def save_config(cfg: dict) -> None:
    """Persist config. Only known keys are written; unknown keys are dropped."""
    out = {k: cfg.get(k, CONFIG_DEFAULTS[k]) for k in CONFIG_DEFAULTS}
    config_path().write_text(json.dumps(out, indent=2), encoding="utf-8")


def set_remote_enabled(enabled: bool) -> dict:
    """Toggle the ``remote_enabled`` flag and persist. Returns the new config."""
    cfg = load_config()
    cfg["remote_enabled"] = bool(enabled)
    save_config(cfg)
    return cfg


def set_remote_backend(backend_type: str | None, **options) -> dict:
    """Set the remote backend spec in config and persist. Returns the new config.

    ``backend_type=None`` clears the remote backend. Otherwise the config stores
    a ``{"type": backend_type, **options}`` dict (options with empty values are
    dropped). The spec is validated via ``configured_remote_backend`` first, so
    an unknown type raises ``ValueError`` before anything is written.
    """
    cfg = load_config()
    if backend_type is None:
        cfg["remote_backend"] = None
    else:
        spec = {"type": backend_type}
        spec.update({k: v for k, v in options.items() if v})
        configured_remote_backend({"remote_backend": spec})  # validate (may raise)
        cfg["remote_backend"] = spec
    save_config(cfg)
    return cfg


# --- Vault detection -----------------------------------------------------

# CLI tools we know how to talk to (or plan to). Detection is purely "is the
# binary on PATH" — it does not run the tools or read any vault state.
KNOWN_VAULT_CLIS: tuple[str, ...] = ("age", "sops", "bw", "op")


def detect_vaults() -> list[str]:
    """Return the subset of KNOWN_VAULT_CLIS that are available on PATH.

    Pure stdlib (``shutil.which``); never runs the binaries. Used to decide
    whether to offer the remote-mirror option to the user at all.
    """
    return [name for name in KNOWN_VAULT_CLIS if shutil.which(name)]


# --- Platform-specific value storage --------------------------------------


def _store_value(name: str, value: str) -> str:
    """Store ``value`` under ``name``. Returns backend tag (``dpapi``/``keyring``)."""
    safe = _safe_name(name)
    if sys.platform == "win32" and HAS_DPAPI:
        enc_path(safe).write_bytes(_dpapi_encrypt(value))
        return "dpapi"
    if HAS_KEYRING:
        keyring.set_password(KEYRING_SERVICE, safe, value)
        return "keyring"
    raise RuntimeError(
        "No credential backend available. Install pywin32 (Windows) or "
        "the 'keyring' package (macOS / Linux)."
    )


def _load_value(name: str) -> str | None:
    safe = _safe_name(name)
    if sys.platform == "win32" and HAS_DPAPI:
        ep = enc_path(safe)
        if not ep.exists():
            return None
        try:
            return _dpapi_decrypt(ep.read_bytes())
        except Exception as exc:  # noqa: BLE001
            print(f"WARN: DPAPI decryption failed: {exc}", file=sys.stderr)
            return None
    if HAS_KEYRING:
        try:
            return keyring.get_password(KEYRING_SERVICE, safe)
        except Exception as exc:  # noqa: BLE001
            print(f"WARN: keyring read failed: {exc}", file=sys.stderr)
            return None
    return None


def _delete_value(name: str) -> tuple[bool, str | None]:
    """Delete value from the active backend.

    Returns ``(deleted, error)`` — ``deleted`` is True if a value was removed
    or was already absent. ``error`` is a string describing a real failure
    that should stop further metadata cleanup, or None on success.
    """
    safe = _safe_name(name)
    if sys.platform == "win32" and HAS_DPAPI:
        ep = enc_path(safe)
        if not ep.exists():
            return True, None  # nothing to delete is fine
        try:
            ep.unlink()
            return True, None
        except OSError as exc:
            return False, f"failed to unlink {ep}: {exc}"
    if HAS_KEYRING:
        try:
            keyring.delete_password(KEYRING_SERVICE, safe)
            return True, None
        except keyring.errors.PasswordDeleteError:
            return True, None  # already absent — fine
        except Exception as exc:  # noqa: BLE001
            return False, f"keyring delete failed: {exc}"
    return False, "no backend available"


def _dpapi_encrypt(plaintext: str) -> bytes:
    if not HAS_DPAPI:
        raise RuntimeError("pywin32 not installed. Run: pip install pywin32")
    blob = win32crypt.CryptProtectData(
        plaintext.encode("utf-8"),
        "secret-paste",
        None,
        None,
        None,
        0,
    )
    return blob


def _dpapi_decrypt(blob: bytes) -> str:
    if not HAS_DPAPI:
        raise RuntimeError("pywin32 not installed. Run: pip install pywin32")
    _desc, data = win32crypt.CryptUnprotectData(blob, None, None, None, 0)
    return data.decode("utf-8")


# --- Metadata + TTL ------------------------------------------------------


def write_credential(
    name: str,
    value: str,
    ttl_hours: int | None,
    persist_to_vault: bool,
) -> str:
    """Store ``value`` and write metadata. Returns backend tag.

    If ``persist_to_vault`` is set AND remote mirroring is enabled in config
    AND a remote backend is configured, the value is additionally pushed to the
    remote backend. A remote failure NEVER corrupts the local store: the local
    write completes first, and any remote error is caught and surfaced only as a
    warning. The returned tag always reflects the local backend.
    """
    backend = _store_value(name, value)
    now = datetime.now(timezone.utc)
    meta = {
        "name": _safe_name(name),
        "created": now.isoformat(),
        "ttl_hours": ttl_hours,  # None = unlimited
        "persist_to_vault": bool(persist_to_vault),
        "backend": backend,
    }
    meta_path(name).write_text(json.dumps(meta, indent=2), encoding="utf-8")

    if persist_to_vault:
        _mirror_to_remote(name, value, ttl_hours, persist_to_vault)

    return backend


def _mirror_to_remote(
    name: str,
    value: str,
    ttl_hours: int | None,
    persist_to_vault: bool,
) -> bool:
    """Best-effort push to the configured remote backend. Never raises.

    Returns True if the value was mirrored, False if mirroring was skipped
    (disabled / not configured) or failed. Any exception from the remote
    backend is swallowed and printed as a warning so the local store stays
    intact.
    """
    cfg = load_config()
    if not cfg.get("remote_enabled"):
        return False
    try:
        remote = configured_remote_backend(cfg)
    except Exception as exc:  # noqa: BLE001
        print(f"WARN: remote mirror skipped (backend config error): {exc}", file=sys.stderr)
        return False
    if remote is None:
        return False
    try:
        remote.put(name, value, ttl_hours=ttl_hours, persist_to_vault=persist_to_vault)
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"WARN: remote mirror failed for {name!r}: {exc}", file=sys.stderr)
        return False


def read_meta(name: str) -> dict | None:
    mp = meta_path(name)
    if not mp.exists():
        return None
    try:
        return json.loads(mp.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


def is_expired(meta: dict) -> bool:
    ttl = meta.get("ttl_hours")
    if ttl is None:
        return False
    try:
        created = datetime.fromisoformat(meta["created"])
    except Exception:  # noqa: BLE001
        return True
    expires = created + timedelta(hours=int(ttl))
    return datetime.now(timezone.utc) >= expires


def expires_at(meta: dict) -> datetime | None:
    ttl = meta.get("ttl_hours")
    if ttl is None:
        return None
    try:
        created = datetime.fromisoformat(meta["created"])
    except Exception:  # noqa: BLE001
        return None
    return created + timedelta(hours=int(ttl))


def list_local() -> list[dict]:
    items = []
    for mp in sorted(store_dir().glob("*.meta.json")):
        try:
            meta = json.loads(mp.read_text(encoding="utf-8"))
            meta["_expired"] = is_expired(meta)
            items.append(meta)
        except Exception:  # noqa: BLE001
            continue
    return items


def delete_local(name: str) -> bool:
    """Delete value (DPAPI / keyring) and then metadata + temp file.

    Metadata is only removed if the value delete succeeded — otherwise we
    leave the metadata in place so the entry stays visible in ``secret-list``
    instead of becoming a ghost (value still in keyring, no metadata to
    point at it).
    """
    value_ok, err = _delete_value(name)
    if not value_ok:
        print(f"WARN: keeping metadata; {err}", file=sys.stderr)
        return False

    deleted = False
    for p in (meta_path(name), tmp_val_path(name)):
        if p.exists():
            try:
                p.unlink()
                deleted = True
            except OSError as exc:
                print(f"WARN: could not unlink {p}: {exc}", file=sys.stderr)
    marker = tmp_val_path(name).with_suffix(".val.expires")
    if marker.exists():
        try:
            marker.unlink()
        except OSError:
            pass
    return deleted


def read_credential(name: str) -> tuple[str | None, dict | None]:
    """Return ``(value, meta)``.

    Side effect: if the entry is expired, the value and metadata are deleted
    so an attacker who steals the DPAPI blob / keyring entry later cannot
    decrypt a credential whose TTL has elapsed.
    """
    meta = read_meta(name)
    if meta is None:
        return None, None
    if is_expired(meta):
        # Opportunistic purge of expired entries.
        try:
            _delete_value(name)
            meta_path(name).unlink(missing_ok=True)
        except Exception:  # noqa: BLE001
            pass
        return None, meta
    value = _load_value(name)
    return value, meta


# --- Tmp file with TTL ---------------------------------------------------

TMP_TTL_MINUTES = 5


def write_tmp_value(name: str, value: str) -> Path:
    """Write value to temp file. Also triggers cleanup of expired temp files.

    The expiry-marker is written *before* the value file, so a crash between
    the two writes leaves at most a stale marker (harmless) — never an
    orphan value file without a TTL.
    """
    cleanup_tmp()
    p = tmp_val_path(name)
    marker = p.with_suffix(".val.expires")
    expires = datetime.now(timezone.utc) + timedelta(minutes=TMP_TTL_MINUTES)
    marker.write_text(expires.isoformat(), encoding="utf-8")
    p.write_text(value, encoding="utf-8", newline="")
    if os.name == "posix":
        try:
            os.chmod(p, 0o600)
        except OSError:
            pass
    return p


def tmp_ttl_remaining(name: str) -> int | None:
    """Remaining lifetime of the temp file in whole seconds.

    Reads the expiry marker (``<name>.val.expires``) and returns the difference
    to ``now``. Never negative — an already-expired (but not yet cleaned up)
    file returns ``0``. Returns ``None`` when no marker exists or its content
    is not a readable timestamp.
    """
    marker = tmp_val_path(name).with_suffix(".val.expires")
    if not marker.exists():
        return None
    try:
        exp = datetime.fromisoformat(marker.read_text(encoding="utf-8").strip())
    except Exception:  # noqa: BLE001
        return None
    remaining = (exp - datetime.now(timezone.utc)).total_seconds()
    return max(0, int(remaining))


def cleanup_tmp() -> None:
    """Remove expired ``.val`` files plus orphan ``.val`` files without a marker."""
    now = datetime.now(timezone.utc)
    d = tmp_dir()
    seen_vals: set[Path] = set()
    for marker in d.glob("*.val.expires"):
        try:
            exp = datetime.fromisoformat(marker.read_text(encoding="utf-8").strip())
            val_file = marker.with_suffix("")  # ".expires" -> ".val"
            seen_vals.add(val_file)
            if now >= exp:
                if val_file.exists():
                    val_file.unlink()
                marker.unlink()
        except Exception:  # noqa: BLE001
            continue
    # Sweep orphan .val files (marker missing → no TTL information). Anything
    # older than TMP_TTL_MINUTES is assumed expired.
    cutoff = now - timedelta(minutes=TMP_TTL_MINUTES)
    for val in d.glob("*.val"):
        if val in seen_vals:
            continue
        try:
            mtime = datetime.fromtimestamp(val.stat().st_mtime, tz=timezone.utc)
            if mtime <= cutoff:
                val.unlink()
        except OSError:
            continue


# --- Format helpers ------------------------------------------------------


def fmt_local(dt: datetime) -> str:
    return dt.astimezone().strftime("%Y-%m-%d %H:%M")


def backend_label() -> str:
    """Human-readable label for the active local backend."""
    if sys.platform == "win32" and HAS_DPAPI:
        return "Windows DPAPI"
    if HAS_KEYRING:
        if sys.platform == "darwin":
            return "macOS Keychain (via keyring)"
        if sys.platform.startswith("linux"):
            return "Linux Secret Service (via keyring)"
        return "keyring"
    return "none"


# --- Vault Plugin Interface ----------------------------------------------


@dataclass
class CredMeta:
    """Metadata for a credential entry (never carries the value itself)."""

    name: str
    created_at: str | None = None
    expires_at: str | None = None
    persist_to_vault: bool = False
    source: str = "local"  # "local" | "vault" | backend-specific id
    extra: dict = field(default_factory=dict)


class VaultBackend(ABC):
    """Pluggable backend for credential storage.

    Implementations must NEVER print or log credential values. ``get`` is the
    only method allowed to return the plaintext value, and only to the caller.

    Capability flag ``supports_read`` advertises whether this backend can serve
    reads. A write-only backend (e.g. a remote mirror you push to but never read
    back from) sets ``supports_read = False``; callers must route reads to a
    readable backend instead and never call ``get`` on it. Use the module-level
    ``backend_get`` helper, which enforces this.
    """

    name: str = "abstract"
    supports_read: bool = True

    @abstractmethod
    def put(
        self,
        name: str,
        value: str,
        ttl_hours: int | None = None,
        persist_to_vault: bool = False,
    ) -> None:
        """Store ``value`` under ``name``. Overwrites existing entries."""

    @abstractmethod
    def get(self, name: str) -> str | None:
        """Return plaintext value or ``None`` if missing/expired."""

    @abstractmethod
    def delete(self, name: str) -> bool:
        """Delete the entry. Returns True if something was deleted."""

    @abstractmethod
    def list(self) -> list[CredMeta]:
        """Return metadata for all entries. Never returns values."""


class WriteOnlyError(RuntimeError):
    """Raised when a write-only backend is asked to read a credential."""


def backend_get(backend: VaultBackend, name: str) -> str | None:
    """Read a credential through a backend, enforcing the read capability.

    Raises ``WriteOnlyError`` if the backend declares ``supports_read = False``
    instead of calling its ``get``. This is the single choke point so that no
    code path can accidentally read from a write-only mirror.
    """
    if not getattr(backend, "supports_read", True):
        raise WriteOnlyError(
            f"Backend {backend.name!r} is write-only and cannot be read from."
        )
    return backend.get(name)


class LocalDPAPIBackend(VaultBackend):
    """Windows-only: per-user DPAPI-encrypted blob on disk + JSON metadata."""

    name = "local-dpapi"

    def put(
        self,
        name: str,
        value: str,
        ttl_hours: int | None = None,
        persist_to_vault: bool = False,
    ) -> None:
        write_credential(name, value, ttl_hours, persist_to_vault)

    def get(self, name: str) -> str | None:
        value, _meta = read_credential(name)
        return value

    def delete(self, name: str) -> bool:
        return delete_local(name)

    def list(self) -> list[CredMeta]:
        return [_meta_to_credmeta(m, "local-dpapi") for m in list_local()]


class KeyringBackend(VaultBackend):
    """macOS / Linux: value in OS keyring, metadata JSON on disk."""

    name = "local-keyring"

    def put(
        self,
        name: str,
        value: str,
        ttl_hours: int | None = None,
        persist_to_vault: bool = False,
    ) -> None:
        write_credential(name, value, ttl_hours, persist_to_vault)

    def get(self, name: str) -> str | None:
        value, _meta = read_credential(name)
        return value

    def delete(self, name: str) -> bool:
        return delete_local(name)

    def list(self) -> list[CredMeta]:
        return [_meta_to_credmeta(m, "local-keyring") for m in list_local()]


def _meta_to_credmeta(m: dict, source: str) -> CredMeta:
    exp = expires_at(m)
    return CredMeta(
        name=m["name"],
        created_at=m.get("created"),
        expires_at=exp.isoformat() if exp else None,
        persist_to_vault=bool(m.get("persist_to_vault")),
        source=source,
        extra={"_expired": bool(m.get("_expired"))},
    )


def default_backend() -> VaultBackend:
    """Return the default backend for the current platform.

    Raises ``RuntimeError`` if no backend is available (missing pywin32 on
    Windows or missing ``keyring`` on macOS / Linux).
    """
    if sys.platform == "win32" and HAS_DPAPI:
        return LocalDPAPIBackend()
    if HAS_KEYRING:
        return KeyringBackend()
    raise RuntimeError(
        "No credential backend available. On Windows: pip install pywin32. "
        "On macOS / Linux: pip install keyring (and on Linux a Secret Service "
        "provider such as gnome-keyring or KeePassXC)."
    )


# --- Remote backends -----------------------------------------------------


def remote_dir() -> Path:
    """Directory holding age-encrypted remote-mirror entries."""
    p = store_dir() / "remote"
    p.mkdir(parents=True, exist_ok=True)
    if os.name == "posix":
        try:
            os.chmod(p, 0o700)
        except OSError:
            pass
    return p


class SopsAgeBackend(VaultBackend):
    """Write-only, file-based remote mirror using the ``age`` CLI (skeleton).

    Each ``put`` writes one age-encrypted file under ``store_dir()/remote/``.
    This is intentionally a skeleton: it implements ``put`` (real age
    encryption) and declares itself write-only — ``get`` is not supported, so
    the credential is mirrored out but never read back through this backend.
    A full sops-managed, syncable remote is future work (see ROADMAP.md).

    The backend needs an age recipient (public key, ``age1...``) to encrypt to.
    If ``age`` is not on PATH, or no recipient is configured, ``put`` raises a
    clear error rather than crashing or silently dropping the value.
    """

    name = "sops-age"
    supports_read = False

    def __init__(self, recipient: str | None = None):
        self.recipient = recipient

    def _entry_path(self, name: str) -> Path:
        return remote_dir() / f"{_safe_name(name)}.age"

    def put(
        self,
        name: str,
        value: str,
        ttl_hours: int | None = None,
        persist_to_vault: bool = False,
    ) -> None:
        import subprocess

        if not self.recipient:
            raise RuntimeError(
                "sops-age backend has no recipient configured. Set an age "
                "recipient (public key 'age1...') before mirroring."
            )
        age_bin = shutil.which("age")
        if age_bin is None:
            raise RuntimeError(
                "The 'age' CLI was not found on PATH. Install age "
                "(https://github.com/FiloSottile/age) to use the sops-age backend."
            )
        out_path = self._entry_path(name)
        try:
            # Encrypt stdin -> file. The plaintext is passed via stdin, never
            # as an argument, so it does not appear in the process table.
            subprocess.run(
                [age_bin, "--encrypt", "--recipient", self.recipient, "--output", str(out_path)],
                input=value.encode("utf-8"),
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or b"").decode("utf-8", "replace").strip()
            raise RuntimeError(f"age encryption failed: {stderr or exc}") from exc
        if os.name == "posix":
            try:
                os.chmod(out_path, 0o600)
            except OSError:
                pass

    def get(self, name: str) -> str | None:
        raise NotImplementedError(
            "sops-age is a write-only backend; reads must come from the local store."
        )

    def delete(self, name: str) -> bool:
        p = self._entry_path(name)
        if p.exists():
            try:
                p.unlink()
                return True
            except OSError:
                return False
        return False

    def list(self) -> list[CredMeta]:
        items: list[CredMeta] = []
        for f in sorted(remote_dir().glob("*.age")):
            items.append(CredMeta(name=f.stem, source=self.name))
        return items


def configured_remote_backend(cfg: dict | None = None) -> VaultBackend | None:
    """Build the remote backend described by config, or None if not configured.

    The ``remote_backend`` config value may be:
      * ``None`` — no remote backend (returns None),
      * a string — the backend type name (e.g. ``"sops-age"``),
      * a dict — ``{"type": ..., <backend-specific options>}`` (e.g. an age
        ``recipient`` for ``sops-age``).

    Raises ``ValueError`` for an unknown backend type so misconfiguration is
    visible rather than silently dropping writes.
    """
    if cfg is None:
        cfg = load_config()
    spec = cfg.get("remote_backend")
    if not spec:
        return None
    if isinstance(spec, str):
        btype, opts = spec, {}
    elif isinstance(spec, dict):
        btype = spec.get("type")
        opts = {k: v for k, v in spec.items() if k != "type"}
    else:
        raise ValueError(f"Invalid remote_backend config: {spec!r}")

    if btype == "sops-age":
        return SopsAgeBackend(recipient=opts.get("recipient"))
    raise ValueError(f"Unknown remote backend type: {btype!r}")


# Stubs for future remote/portable backends — see ROADMAP.md:
#
# class BitwardenBackend(VaultBackend):   # bw CLI
# class OnePasswordBackend(VaultBackend): # op CLI


# --- One-time sharing (DESIGN SKELETON — NOT WIRED IN) -------------------
#
# Concept + threat model + open decisions: docs/one-time-sharing.md
#
# This is a deliberately non-functional skeleton. It is NOT imported by any
# default code path and changes no existing behavior — it only fixes the
# *shape* of the interface so the server approach can be chosen before any
# server is built. Every method raises NotImplementedError pointing at the
# design doc. Do not wire this into the CLI flow until the open decisions in
# the doc are settled.
#
# Why a separate interface (not VaultBackend): one-time sharing is
# write-then-read-once-then-gone. Its `reveal` is destructive and non-
# idempotent, which violates the "safe, named, idempotent read" contract that
# VaultBackend.get / backend_get guarantee. Keeping it separate keeps that
# guarantee intact and makes the destructive semantics explicit in the type.


@dataclass
class ShareLink:
    """Result of creating a one-time share. Carries NO plaintext or key state.

    ``url`` is the full link to hand over, including the ``#k=...`` fragment
    that holds the decryption key. The fragment is never sent to the server
    (RFC 3986 §3.5), so the server only ever sees ``record_id`` + ciphertext.
    """

    url: str
    record_id: str
    expires_at: str | None = None  # ISO-8601 server-side expiry if unopened


class ShareBackend(ABC):
    """Pluggable backend for one-time, single-view secret *sharing* (skeleton).

    Contrast with ``VaultBackend`` (named, re-readable local storage): a
    ``ShareBackend`` uploads client-encrypted ciphertext to a zero-knowledge
    server and returns a one-time link. ``reveal`` is destructive — the server
    deletes its copy as part of serving the read.

    Trust requirement (see docs/one-time-sharing.md): the server stores only
    ciphertext; the decryption key lives solely in the URL fragment and is
    never transmitted. Implementations MUST encrypt client-side before upload
    and MUST NEVER send the key or plaintext to the server.

    This is a skeleton: both methods raise ``NotImplementedError``. No concrete
    backend ships yet — the server approach is an open maintainer decision.
    """

    name: str = "abstract-share"

    @abstractmethod
    def create(self, value: str, *, ttl_seconds: int | None = None) -> ShareLink:
        """Encrypt ``value`` client-side, upload only the ciphertext, and return
        a one-time link. The plaintext and the key never leave the client except
        inside the returned URL's fragment.

        ``ttl_seconds`` is the server-side expiry for an *unopened* link
        (``None`` = backend default).
        """
        raise NotImplementedError(
            "One-time sharing is not implemented yet. See docs/one-time-sharing.md "
            "(server approach is an open maintainer decision)."
        )

    @abstractmethod
    def reveal(self, url: str) -> str:
        """Fetch + decrypt the secret behind ``url`` exactly once, then let the
        server destroy its copy. Raises if already viewed / expired / not found.

        Destructive and non-idempotent by design — calling twice must not return
        the value twice.
        """
        raise NotImplementedError(
            "One-time sharing is not implemented yet. See docs/one-time-sharing.md "
            "(server approach is an open maintainer decision)."
        )


def configured_share_backend(cfg: dict | None = None) -> ShareBackend | None:
    """Return the configured one-time-share backend, or None.

    Skeleton: no share backend type is registered yet, so this always returns
    None (one-time sharing is not configured). It mirrors
    ``configured_remote_backend`` so wiring it in later is a small, obvious
    change once the server approach is chosen. See docs/one-time-sharing.md.
    """
    return None
