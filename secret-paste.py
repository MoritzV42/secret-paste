"""secret-paste: GUI dialog for entering a credential.

Usage:
  secret-paste <KEY_NAME> [--ttl=24] [--persist] [--desc="Brevo API key"]

Stores DPAPI-encrypted under %LOCALAPPDATA%\\secret-paste\\.

A "Mirror to remote backend" checkbox is shown in the dialog but disabled in
this release. Remote backends (Bitwarden, 1Password, SSH-vault) are planned
via the ``VaultBackend`` plugin interface â€” see ROADMAP.md.
"""
from __future__ import annotations

import argparse
import sys
import tkinter as tk
from tkinter import ttk, messagebox

import _common as cc


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="secret-paste",
        description="Opens a GUI dialog to paste a credential and store it DPAPI-encrypted.",
    )
    p.add_argument("name", help="Key name (e.g. BREVO_KEY)")
    p.add_argument("--ttl", type=int, default=24,
                   help="TTL in hours (default 24). Ignored with --persist.")
    p.add_argument("--persist", action="store_true",
                   help="Store permanently (no TTL).")
    p.add_argument("--desc", "--description", dest="desc", default="",
                   help="Optional description shown in the dialog.")
    return p.parse_args(argv)


def show_dialog(key_name: str, description: str,
                default_persist: bool) -> tuple[bool, str, bool, bool]:
    """Modal dialog. Returns (ok, value, vault_checkbox, persist_checkbox)."""
    root = tk.Tk()
    root.title(f"Credential Paste: {key_name}")
    root.attributes("-topmost", True)
    root.lift()
    root.focus_force()

    # Minimum size
    try:
        root.geometry("520x300")
    except Exception:
        pass

    frame = ttk.Frame(root, padding=16)
    frame.pack(fill="both", expand=True)

    header = ttk.Label(frame, text=f"Enter credential: {key_name}",
                       font=("Segoe UI", 12, "bold"))
    header.pack(anchor="w")

    if description:
        desc_lbl = ttk.Label(frame, text=description, wraplength=480,
                             foreground="#555")
        desc_lbl.pack(anchor="w", pady=(4, 8))
    else:
        ttk.Label(frame,
                  text="Paste the value (Ctrl+V). It will be stored locally, DPAPI-encrypted.",
                  foreground="#555", wraplength=480).pack(anchor="w", pady=(4, 8))

    value_var = tk.StringVar()
    show_var = tk.BooleanVar(value=False)
    persist_var = tk.BooleanVar(value=default_persist)
    vault_var = tk.BooleanVar(value=False)

    entry = ttk.Entry(frame, textvariable=value_var, show="*", width=60)
    entry.pack(fill="x", pady=(4, 4))
    entry.focus_set()

    def toggle_show():
        entry.configure(show="" if show_var.get() else "*")

    ttk.Checkbutton(frame, text="Show value", variable=show_var,
                    command=toggle_show).pack(anchor="w")

    ttk.Separator(frame).pack(fill="x", pady=8)

    # Remote-backend checkbox: visible but disabled until plugin backends ship.
    vault_check = ttk.Checkbutton(
        frame,
        text="Also mirror to remote backend (coming soon)",
        variable=vault_var,
        state="disabled",
    )
    vault_check.pack(anchor="w")

    # Tooltip-style hint underneath the disabled checkbox.
    ttk.Label(
        frame,
        text="Remote backends coming soon (Bitwarden / 1Password / SSH-vault). See ROADMAP.md.",
        foreground="#888",
        font=("Segoe UI", 8, "italic"),
        wraplength=480,
    ).pack(anchor="w", padx=(22, 0))

    ttk.Checkbutton(
        frame,
        text="Store permanently (no local TTL)",
        variable=persist_var,
    ).pack(anchor="w", pady=(6, 4))

    result: dict = {"ok": False}

    def on_ok(event=None):
        if not value_var.get():
            messagebox.showwarning("Empty", "Please enter a value.",
                                   parent=root)
            return
        result["ok"] = True
        result["value"] = value_var.get()
        result["vault"] = vault_var.get()
        result["persist"] = persist_var.get()
        root.destroy()

    def on_cancel(event=None):
        result["ok"] = False
        root.destroy()

    btn_frame = ttk.Frame(frame)
    btn_frame.pack(fill="x", pady=(12, 0))
    ttk.Button(btn_frame, text="Cancel", command=on_cancel).pack(side="right")
    ttk.Button(btn_frame, text="OK", command=on_ok).pack(side="right", padx=(0, 8))

    root.bind("<Return>", on_ok)
    root.bind("<Escape>", on_cancel)
    root.protocol("WM_DELETE_WINDOW", on_cancel)

    root.mainloop()

    if not result.get("ok"):
        return False, "", False, False
    return True, result["value"], bool(result.get("vault")), bool(result.get("persist"))


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        # Validate name
        cc._safe_name(args.name)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if sys.platform != "win32":
        print(
            "ERROR: secret-paste is currently Windows-only. "
            "Linux/Mac via keyring planned â€” see ROADMAP.md.",
            file=sys.stderr,
        )
        return 1

    if not cc.HAS_DPAPI:
        print("ERROR: pywin32 missing. Please run: pip install pywin32",
              file=sys.stderr)
        return 1

    ok, value, vault, persist_flag = show_dialog(
        args.name, args.desc, default_persist=args.persist
    )
    if not ok:
        print("Cancelled.", file=sys.stderr)
        return 1

    ttl_hours = None if (args.persist or persist_flag or vault) else int(args.ttl)
    cc.write_credential(args.name, value, ttl_hours=ttl_hours,
                        persist_to_vault=vault)
    print(f"OK: {args.name} stored locally "
          f"({'permanent' if ttl_hours is None else f'TTL {ttl_hours}h'}).")

    if vault:
        # Reserved for when a remote backend is configured.
        print(
            "NOTE: Remote-mirror requested but no remote backend is configured. "
            "See ROADMAP.md.",
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
