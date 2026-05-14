"""secret-get: Deliver a credential via temp file (NEVER on stdout).

Usage:
  secret-get <KEY_NAME> [--export-env]

Default:
  Writes value to %TEMP%\\secret-paste-tmp\\<name>.val (5-minute TTL).
  Stdout shows ONLY: "OK: <name> available at <path> (5min TTL)"

--export-env:
  Emits a PowerShell snippet that, when dot-sourced, sets $env:<NAME>
  from the temp file. The value is NOT echoed to the terminal â€” it is
  read from the temp file inside the snippet.

Exit codes:
  0 = OK
  1 = Argument error
  2 = MISSING (not found locally)
"""
from __future__ import annotations

import argparse
import sys

import _common as cc


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="secret-get",
        description="Deliver credential via temp file (5min TTL).",
    )
    p.add_argument("name", help="Key name")
    p.add_argument("--export-env", action="store_true",
                   help="Emit PowerShell snippet to stdout: "
                        "$env:<NAME>=(Get-Content <path>). Value not in output.")
    p.add_argument("--no-vault", action="store_true",
                   help="(Reserved) Skip remote-backend fallback. "
                        "No remote backend is configured in this release.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        safe = cc._safe_name(args.name)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    value, _meta = cc.read_credential(args.name)
    source = "local"

    if value is None:
        # No remote backend in this release â€” see ROADMAP.md.
        print(
            f"MISSING: {args.name} not found locally. "
            f"Run secret-paste {args.name} to add it.",
            file=sys.stderr,
        )
        return 2

    tmp_path = cc.write_tmp_value(args.name, value)

    if args.export_env:
        # Value is not in the output. PowerShell snippet reads it from the file.
        env_name = safe.upper().replace("-", "_").replace(".", "_")
        print(
            f"# Source: {source}. File TTL: {cc.TMP_TTL_MINUTES} min.\n"
            f"$env:{env_name} = (Get-Content -Raw -Encoding UTF8 '{tmp_path}').TrimEnd(\"`r`n\")\n"
            f"Write-Host 'OK: $env:{env_name} set from {tmp_path}'"
        )
    else:
        print(f"OK: {args.name} available at {tmp_path} "
              f"({cc.TMP_TTL_MINUTES}min TTL, source={source})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
