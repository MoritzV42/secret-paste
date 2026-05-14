"""secret-paste: GUI dialog for entering a credential.

Usage:
  secret-paste <KEY_NAME> [--ttl=24] [--persist] [--desc="Brevo API key"]

Stores the value via the platform backend:

* Windows: DPAPI-encrypted blob under ``%LOCALAPPDATA%\\secret-paste\\``.
* macOS / Linux: via ``keyring`` (Keychain / libsecret / kwallet).

A "Mirror to remote backend" checkbox is shown in the dialog but disabled in
this release. Remote backends (Bitwarden, 1Password, sops/age) are planned via
the ``VaultBackend`` plugin interface — see ROADMAP.md.
"""

from __future__ import annotations

import argparse
import sys

import secret_paste_core as cc


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="secret-paste",
        description=(
            "Open a GUI dialog to paste a credential and store it locally "
            "via the platform's secure backend (Windows DPAPI / macOS "
            "Keychain / Linux Secret Service)."
        ),
    )
    p.add_argument("name", help="Key name (e.g. BREVO_KEY)")
    p.add_argument(
        "--ttl",
        type=int,
        default=24,
        help="TTL in hours (default 24). Ignored with --persist.",
    )
    p.add_argument(
        "--persist",
        action="store_true",
        help="Store permanently (no TTL).",
    )
    p.add_argument(
        "--desc",
        "--description",
        dest="desc",
        default="",
        help="Optional description shown in the dialog.",
    )
    return p.parse_args(argv)


# Font stack: pick first available per-OS sans-serif.
_FONT_BY_OS = {
    "win32": "Segoe UI",
    "darwin": "SF Pro Text",  # falls back via tk
    "linux": "DejaVu Sans",
}


def _font(weight: str = "normal", size: int = 10) -> tuple:
    family = _FONT_BY_OS.get(sys.platform, "TkDefaultFont")
    return (family, size, weight)


def _apply_theme(root) -> None:
    """Pick a per-OS modern ttk theme. Pure stdlib, no extra deps."""
    from tkinter import ttk

    style = ttk.Style(root)
    available = set(style.theme_names())
    preferred = []
    if sys.platform == "darwin":
        preferred = ["aqua"]
    elif sys.platform == "win32":
        preferred = ["vista", "winnative", "xpnative"]
    else:
        preferred = ["clam"]
    for t in preferred:
        if t in available:
            try:
                style.theme_use(t)
                break
            except Exception:  # noqa: BLE001
                continue
    style.configure("Header.TLabel", font=_font("bold", 13))
    style.configure("Hint.TLabel", foreground="#666", font=_font("normal", 9))
    style.configure("Muted.TLabel", foreground="#999", font=_font("normal", 8))
    style.configure("Backend.TLabel", foreground="#3a7bd5", font=_font("normal", 9))


def show_dialog(
    key_name: str,
    description: str,
    default_persist: bool,
    backend_label: str,
) -> tuple[bool, str, bool, bool]:
    """Modal dialog. Returns ``(ok, value, vault_checkbox, persist_checkbox)``."""
    import tkinter as tk
    from tkinter import ttk

    root = tk.Tk()
    root.title(f"secret-paste: {key_name}")
    _apply_theme(root)
    root.attributes("-topmost", True)
    root.lift()
    root.focus_force()

    try:
        root.geometry("560x340")
        root.minsize(480, 280)
    except Exception:  # noqa: BLE001
        pass

    outer = ttk.Frame(root, padding=18)
    outer.pack(fill="both", expand=True)

    ttk.Label(outer, text=f"Enter credential: {key_name}", style="Header.TLabel").pack(anchor="w")

    ttk.Label(
        outer,
        text=description
        or "Paste the value (Ctrl+V on Win/Linux, ⌘V on macOS). " "Stored locally on this machine.",
        style="Hint.TLabel",
        wraplength=520,
    ).pack(anchor="w", pady=(4, 10))

    value_var = tk.StringVar()
    show_var = tk.BooleanVar(value=False)
    persist_var = tk.BooleanVar(value=default_persist)
    vault_var = tk.BooleanVar(value=False)

    entry = ttk.Entry(outer, textvariable=value_var, show="*", width=60)
    entry.pack(fill="x", pady=(4, 4))
    entry.focus_set()

    err_lbl = ttk.Label(outer, text="", foreground="#d23", style="Hint.TLabel")
    err_lbl.pack(anchor="w")

    def toggle_show():
        entry.configure(show="" if show_var.get() else "*")

    def clear_error(*_):
        if err_lbl.cget("text"):
            err_lbl.configure(text="")

    value_var.trace_add("write", clear_error)

    ttk.Checkbutton(outer, text="Show value", variable=show_var, command=toggle_show).pack(
        anchor="w"
    )

    ttk.Separator(outer).pack(fill="x", pady=10)

    ttk.Checkbutton(
        outer,
        text="Also mirror to remote backend (coming soon)",
        variable=vault_var,
        state="disabled",
    ).pack(anchor="w")
    ttk.Label(
        outer,
        text="Remote backends (Bitwarden / 1Password / sops) planned — see ROADMAP.md.",
        style="Muted.TLabel",
        wraplength=520,
    ).pack(anchor="w", padx=(22, 0))

    ttk.Checkbutton(
        outer,
        text="Store permanently (no local TTL)",
        variable=persist_var,
    ).pack(anchor="w", pady=(6, 4))

    ttk.Label(outer, text=f"Backend: {backend_label}", style="Backend.TLabel").pack(
        anchor="w", pady=(12, 0)
    )

    result: dict = {"ok": False}

    def on_ok(event=None):
        if not value_var.get():
            err_lbl.configure(text="Please enter a value.")
            entry.focus_set()
            return
        result["ok"] = True
        result["value"] = value_var.get()
        result["vault"] = vault_var.get()
        result["persist"] = persist_var.get()
        root.destroy()

    def on_cancel(event=None):
        result["ok"] = False
        root.destroy()

    btn_frame = ttk.Frame(outer)
    btn_frame.pack(fill="x", pady=(14, 0))
    ttk.Button(btn_frame, text="Cancel", command=on_cancel).pack(side="right")
    ttk.Button(btn_frame, text="OK", command=on_ok).pack(side="right", padx=(0, 8))

    root.bind("<Return>", on_ok)
    root.bind("<Escape>", on_cancel)
    root.protocol("WM_DELETE_WINDOW", on_cancel)

    root.mainloop()

    if not result.get("ok"):
        return False, "", False, False
    return (
        True,
        result["value"],
        bool(result.get("vault")),
        bool(result.get("persist")),
    )


def show_toast(key_name: str, ttl_text: str, backend_label: str) -> None:
    """Brief auto-closing confirmation popup after a successful paste."""
    try:
        import tkinter as tk
        from tkinter import ttk
    except ImportError:
        return
    try:
        root = tk.Tk()
    except Exception:  # noqa: BLE001
        return
    _apply_theme(root)
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    root.configure(bg="#2a2a2a")

    frame = ttk.Frame(root, padding=14)
    frame.pack()
    ttk.Label(
        frame,
        text=f"[OK] Stored: {key_name}",
        style="Header.TLabel",
    ).pack(anchor="w")
    ttk.Label(
        frame,
        text=f"{ttl_text} · {backend_label}",
        style="Hint.TLabel",
    ).pack(anchor="w", pady=(2, 0))

    root.update_idletasks()
    w = root.winfo_width()
    sw = root.winfo_screenwidth()
    root.geometry(f"+{sw - w - 24}+{24}")
    root.after(1800, root.destroy)
    try:
        root.mainloop()
    except Exception:  # noqa: BLE001
        pass


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        cc._safe_name(args.name)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    try:
        cc.default_backend()  # surface backend errors early
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    backend_label = cc.backend_label()

    ttl_cli = args.ttl
    if args.persist and ttl_cli != 24:
        # 24 is the default — only warn when user passed a real value.
        print(
            f"WARN: --ttl={ttl_cli} ignored because --persist is set.",
            file=sys.stderr,
        )

    ok, value, vault, persist_flag = show_dialog(
        args.name,
        args.desc,
        default_persist=args.persist,
        backend_label=backend_label,
    )
    if not ok:
        print("Cancelled.", file=sys.stderr)
        return 1

    if persist_flag and not args.persist and ttl_cli != 24:
        print(
            f"WARN: --ttl={ttl_cli} ignored because 'Store permanently' was "
            "checked in the dialog.",
            file=sys.stderr,
        )

    ttl_hours = None if (args.persist or persist_flag or vault) else int(args.ttl)
    cc.write_credential(args.name, value, ttl_hours=ttl_hours, persist_to_vault=vault)
    ttl_text = "permanent" if ttl_hours is None else f"TTL {ttl_hours}h"
    print(f"OK: {args.name} stored locally ({ttl_text}, {backend_label}).")

    if vault:
        print(
            "NOTE: Remote-mirror requested but no remote backend is " "configured. See ROADMAP.md.",
            file=sys.stderr,
        )

    show_toast(args.name, ttl_text, backend_label)
    return 0


if __name__ == "__main__":
    sys.exit(main())
