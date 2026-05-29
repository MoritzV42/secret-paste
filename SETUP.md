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
Please install and set up the "secret-paste" tool for me. Work step by step and
explain what you do.

1. Detect my OS and check that Python 3.10+ and pipx are available. If pipx is
   missing, install it (python -m pip install --user pipx && python -m pipx
   ensurepath) and tell me to reopen the shell if PATH changed.
2. Install the tool:  pipx install secret-paste
3. Verify it: run  secret-get --help  and  secret-paste --show-config  and show
   me the output.
4. Check whether I already have a local secret manager on PATH by running:
       secret-paste --show-config
   It prints "detected vault CLIs". The tool understands: age, sops, bw
   (Bitwarden), op (1Password).
5. IF at least one vault CLI was detected, ASK me (do NOT decide for me) whether
   I want to enable the OPTIONAL write-only remote mirror. Explain clearly and
   honestly before I answer:
     - Everything stays LOCAL on my machine. Nothing is uploaded anywhere and
       the tool's author receives nothing.
     - The mirror is WRITE-ONLY: secret-paste can only write into the vault,
       never read back from it. My AI agent keeps reading secrets only from the
       short-lived local temp file, exactly as without the mirror.
     - It is fully optional and can be turned off again at any time.
   IF I say yes and "age" is available, ask me for my age recipient (public key,
   starts with "age1...") and run:
       secret-paste --set-remote sops-age --recipient age1...
       secret-paste --enable-remote
   IF I say no, or no vault CLI was detected, do nothing here — the mirror option
   simply stays hidden and uninstalled. Do not nag me about it.
6. Show me the basic usage:
     - Store a secret:        secret-paste BREVO_KEY
       (a small GUI dialog opens; I paste the value there, it never touches the
       chat transcript)
     - Use it in a command:   secret-get BREVO_KEY --print-path
       (prints the path to a temp file that holds the value for ~5 minutes;
       read the file, never echo the value)
     - Machine-readable:      secret-get BREVO_KEY --json
7. Confirm everything works and summarise what you configured.
```

---

## 2. Manual install (no AI agent)

```bash
pipx install secret-paste     # or: pip install --user secret-paste
secret-get --help
secret-paste --show-config
```

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
