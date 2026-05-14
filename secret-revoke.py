"""secret-revoke: Delete a credential locally.

Usage:
  secret-revoke <KEY_NAME>
"""
from __future__ import annotations

import argparse
import sys

import _common as cc


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="secret-revoke",
        description="Delete a credential from the local store.",
    )
    p.add_argument("name", help="Key name")
    p.add_argument("--keep-vault", action="store_true",
                   help="(Reserved) Do not delete remote-backend entry. "
                        "No remote backend is configured in this release.")
    p.add_argument("--vault-only", action="store_true",
                   help="(Reserved) Only delete remote-backend entry. "
                        "No remote backend is configured in this release.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        cc._safe_name(args.name)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.vault_only:
        print(
            "NOTE: --vault-only requires a remote backend, "
            "which is not configured in this release. See ROADMAP.md.",
            file=sys.stderr,
        )
        return 1

    local_deleted = cc.delete_local(args.name)

    if not local_deleted:
        print(f"Nothing deleted (key '{args.name}' not found).",
              file=sys.stderr)
        return 1

    print(f"OK: {args.name} deleted (local).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
