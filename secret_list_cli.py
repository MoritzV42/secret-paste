"""secret-list: Show available credentials (names + meta, NEVER values).

Usage:
  secret-list
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime

import secret_paste_core as cc


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="secret-list",
        description="List all locally stored credentials (names + meta, no values).",
    )
    p.add_argument(
        "--vault",
        action="store_true",
        help="(Reserved) Also list remote-backend entries. "
        "No remote backend is configured in this release.",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])

    local = cc.list_local()

    # Table columns
    header = ("Key Name", "Source", "Created", "Expires", "Persist Vault")
    widths = [max(len(header[0]), 18), 8, 16, 19, 14]

    rows: list[tuple[str, str, str, str, str]] = []
    for m in local:
        created = datetime.fromisoformat(m["created"])
        exp = cc.expires_at(m)
        if exp is None:
            exp_str = "-"
        elif m.get("_expired"):
            exp_str = "EXPIRED"
        else:
            exp_str = cc.fmt_local(exp)
        rows.append(
            (
                m["name"],
                m.get("backend", "local"),
                cc.fmt_local(created),
                exp_str,
                "Yes" if m.get("persist_to_vault") else "No",
            )
        )

    # Adjust column widths
    all_rows = [header] + rows
    for r in all_rows:
        for i, cell in enumerate(r):
            widths[i] = max(widths[i], len(str(cell)))

    def fmt_row(r: tuple) -> str:
        return "  ".join(str(r[i]).ljust(widths[i]) for i in range(len(r)))

    print(fmt_row(header))
    print("  ".join("-" * w for w in widths))
    if not rows:
        print("(no credentials)")
    else:
        for r in rows:
            print(fmt_row(r))

    if args.vault:
        print(
            "\nNOTE: --vault is reserved for future remote backends. "
            "No remote backend is configured in this release. See ROADMAP.md.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
