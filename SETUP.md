# AI-Assisted Setup

`secret-paste` is small and installs in seconds. The fastest way is to let the
AI coding agent you already use (Claude Code, Cursor, Copilot CLI, …) install
and configure it **tailored to your machine** — including whether you want the
optional, write-only vault mirror.

There is no wizard binary to run. "The installer" is just the prompt below: you
hand it to your agent, and the agent does the work.

---

## 1. Paste this to your AI coding agent

Copy the whole block and paste it into your agent:

```text
Please install and set up the "secret-paste" tool on my machine. Work step by
step, explain each step, and ASK me whenever a decision is mine. Do NOT assume my
operating system — detect it. If you already know my OS from prior context, say
so and still verify it.

WHAT THIS TOOL DOES (context for you):
secret-paste lets me hand you a secret (API key, token, password) WITHOUT the
value ever appearing in our chat. I paste it into a small local GUI dialog; you
later retrieve it with `secret-get`, which writes it to a short-lived temp file
and never prints the value. Repo: https://github.com/MoritzV42/secret-paste

1. DETECT ENVIRONMENT — report before changing anything:
   - OS (Windows / macOS / Linux) + architecture.
   - Python >= 3.10  (`python3 --version` or `python --version`).
   - pipx            (`pipx --version`).
   - GUI toolkit     (`python3 -c "import tkinter"`) — REQUIRED even for the
     plain fallback dialog. On macOS the system Python often lacks it.

2. INSTALL ONLY WHAT IS MISSING (per OS):
   - Windows: Python via `winget install Python.Python.3.12`; pipx via
     `python -m pip install --user pipx; python -m pipx ensurepath`.
     (tkinter ships with the winget/python.org build.)
   - macOS: `brew install python python-tk pipx` then `pipx ensurepath`.
     python-tk is REQUIRED or the dialog will not open.
   - Linux: install python3 + python3-pip + pipx via the distro manager and
     `sudo apt install python3-tk` (or the distro equivalent) for the GUI;
     `pipx ensurepath`. The keyring backend needs a running Secret Service
     (GNOME Keyring / KWallet) in a headed session.
   - If PATH changed after `ensurepath`, tell me to reopen the shell, then continue.

3. INSTALL THE TOOL (from GitHub — it is not on PyPI):
       pipx install "secret-paste[gui] @ git+https://github.com/MoritzV42/secret-paste"
   The [gui] extra pulls CustomTkinter for the modern dark dialog; without it a
   plain-Tk fallback is used.

4. VERIFY:
   - `secret-get --help` prints usage.
   - `secret-paste --show-config` prints remote_enabled / backend (expect remote
     OFF by default).
   - GUI smoke test: run `secret-paste TEST_KEY`; I paste a throwaway value + OK.
     Then `secret-list` must show TEST_KEY with its backend (dpapi on Windows,
     keyring on macOS/Linux) and a TTL. Then `secret-revoke TEST_KEY`.
   - Tell me the detected backend and CONFIRM the value never appeared in chat.

5. OPTIONAL WRITE-ONLY REMOTE MIRROR — ASK me first, do NOT decide:
   `secret-paste --show-config` lists "detected vault CLIs" (age, sops, bw, op).
   Explain honestly: everything stays local; the mirror is WRITE-ONLY (secret-get
   never reads from it); fully optional; off by default; nothing goes to the
   author or any third party. IF I say yes and `age` is present, ask for my age
   recipient (`age1...`) and run:
       secret-paste --set-remote sops-age --recipient age1...
       secret-paste --enable-remote
   IF I say no or no CLI is detected: do nothing, don't nag.

6. OPTIONAL AGENT SKILL — ASK me first:
   Offer to install the bundled skill so future chats auto-trigger secret-paste
   when a secret is needed: run `secret-paste-install-skill` and tell me where it
   landed.

7. SUMMARISE: OS, Python/pipx versions, install path, detected backend, whether
   the mirror + skill were configured, and the one command I run next time I want
   to hand you a secret:  secret-paste <NAME>
```

---

## 2. Manual install (no AI agent)

```bash
# Not on PyPI yet — install from GitHub:
pipx install "secret-paste[gui] @ git+https://github.com/MoritzV42/secret-paste"
secret-get --help
secret-paste --show-config
```

macOS needs Tk for the dialog: `brew install python-tk`. Debian/Ubuntu: `sudo apt install python3-tk`.

Store and use a secret:

```bash
secret-paste BREVO_KEY                 # GUI dialog → paste the value
secret-get BREVO_KEY --print-path      # → path to a temp file (value never on stdout)
```

### Optional: write-only remote mirror

Only if you keep your own vault and want a second copy written there. It is off
by default. Today an `age`-based, file-based backend ships as the reference:

```bash
secret-paste --set-remote sops-age --recipient age1yourpublickey
secret-paste --enable-remote
secret-paste --disable-remote          # turn it back off anytime
```

The mirror is **write-only by design** — `secret-paste` can only write to it,
never read from it.

---

## 3. Privacy in one line

Everything is local to your machine, the value never enters the chat transcript,
the optional vault mirror is write-only, and nothing is ever sent to the author
or any third party.

---

## 4. Troubleshooting

### macOS: Homebrew Python has a broken `pyexpat` (pip / XML errors)

**Symptom.** On recent macOS the Homebrew Pythons (seen on both 3.13 and 3.14)
can ship a `pyexpat` that fails to import. You'll see errors when `pip` or any
XML code runs, typically a dynamic-link failure mentioning **`libexpat`** and a
missing symbol like **`_XML…ActivationThreshold`** — the bundled `pyexpat.so`
expects a newer system `/usr/lib/libexpat` than the OS provides. This breaks
**every Homebrew-Python tool**, not just `secret-paste`: `pipx install …` can
fail, and `import pyexpat` (or anything that imports it) raises an
`ImportError` about the missing symbol.

**Fix — install secret-paste under a [uv](https://docs.astral.sh/uv/)-managed
Python.** uv ships a standalone Python build with a working `expat` (and Tk),
so it sidesteps the broken Homebrew interpreter entirely:

```bash
uv python install 3.13
uv tool install secret-paste
```

This was confirmed end-to-end on macOS 26.2 (install completed, backend
detected: `keychain`).

**Alternative — pipx pinned to the uv Python.** If you prefer `pipx`, point it
at the uv-managed interpreter instead of the broken Homebrew one:

```bash
uv python install 3.13
pipx install --python "$(uv python find 3.13)" secret-paste
```

**GUI window.** `secret-paste` opens a Tk dialog; on macOS that needs Tk. A
uv-managed Python includes it. If you're on a different Python that lacks it,
install Tk as covered in [§2 Manual install](#2-manual-install-no-ai-agent):
`brew install python-tk`.
