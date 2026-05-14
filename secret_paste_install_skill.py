"""Install the secret-paste Claude skill into ``~/.claude/skills/``.

Run once after ``pipx install secret-paste`` (or ``pip install secret-paste``)
so any Claude-Code session on this machine automatically knows to request
credentials via secret-paste instead of asking for a chat paste.

Idempotent — re-running just refreshes the skill file.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from importlib import resources
from pathlib import Path

SKILL_FILENAME = "secret-paste.md"


def _packaged_skill() -> Path:
    """Locate the bundled ``secret-paste.md`` skill file.

    Searches first in the installed package data, then falls back to a
    sibling ``skill/`` directory next to this module (editable installs +
    running directly from the repo).
    """
    # Installed via wheel: skill is shipped as package data.
    try:
        with resources.as_file(resources.files("secret_paste_skill").joinpath(SKILL_FILENAME)) as p:
            if p.exists():
                return p
    except (ModuleNotFoundError, FileNotFoundError):
        pass

    # Editable install or run-from-repo: look next to this module.
    here = Path(__file__).resolve().parent
    candidate = here / "secret_paste_skill" / SKILL_FILENAME
    if candidate.exists():
        return candidate

    raise FileNotFoundError(
        f"Could not locate bundled {SKILL_FILENAME}. " "Reinstall secret-paste or report a bug."
    )


def skills_dir() -> Path:
    """Target directory: ``~/.claude/skills/``.

    Claude Code reads user-level skills from this path on every OS (Windows
    uses ``%USERPROFILE%\\.claude\\skills\\``, which ``Path.home()`` resolves
    identically).
    """
    return Path.home() / ".claude" / "skills"


def install(force: bool = False) -> Path:
    src = _packaged_skill()
    dst_dir = skills_dir()
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / SKILL_FILENAME

    if (
        dst.exists()
        and not force
        and dst.read_text(encoding="utf-8") == src.read_text(encoding="utf-8")
    ):
        print(f"OK: skill already up to date at {dst}")
        return dst

    shutil.copyfile(src, dst)
    print(f"OK: installed Claude skill to {dst}")
    print("Open a new Claude-Code session (or run /reload-skills) so the " "skill becomes active.")
    return dst


def uninstall() -> bool:
    dst = skills_dir() / SKILL_FILENAME
    if not dst.exists():
        print(f"Nothing to remove (no skill at {dst}).", file=sys.stderr)
        return False
    dst.unlink()
    print(f"OK: removed Claude skill from {dst}")
    return True


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="secret-paste-install-skill",
        description=(
            "Install the secret-paste Claude skill so any Claude-Code "
            "session on this machine knows to use secret-paste instead "
            "of asking you to paste credentials into chat."
        ),
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing skill file even if contents differ.",
    )
    p.add_argument(
        "--uninstall",
        action="store_true",
        help="Remove the skill from ~/.claude/skills/.",
    )
    args = p.parse_args(argv or sys.argv[1:])

    if args.uninstall:
        return 0 if uninstall() else 1
    try:
        install(force=args.force)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
