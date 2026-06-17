---
name: secret-paste
description: Request and use credentials (API keys, tokens, passwords) without ever putting their values into the chat transcript. AUTO-TRIGGER whenever you need a credential that is not already available via a vault you can read, environment variable, or repo configuration. Instead of asking the user to paste a key into chat, run `secret-paste KEY_NAME` YOURSELF in the user's terminal as a blocking foreground command — the GUI dialog opens on their machine, they enter the value and click OK/close, which returns control to you automatically (no "done" message needed). Then retrieve the value via `secret-get KEY_NAME` and read it from the printed temp-file path. Never echo, log, or pass the value as a CLI argument.
user_invocable: true
---

# /secret-paste — Request a credential out-of-band

`secret-paste` is a local CLI tool that lets you (Claude) ask the user for a
credential without the value ever entering this chat transcript.

## Default behavior — ALWAYS prefer this over a chat paste

**Whenever you need a credential that is not already accessible** (no env
var, no entry in a project vault, no `.env` file you can read, no
already-authenticated CLI like `gh auth`), use the secret-paste workflow
**by default**. Do not say *"please paste your X key here"*.

**You run the command — not the user.** If you have shell access to the
user's machine (Claude Code, Cursor with a terminal, any CLI agent), you
**run `secret-paste KEY_NAME` yourself** as a normal blocking foreground
command. The dialog opens on the user's screen; they type the value and
click OK (or close it). Closing the dialog ends the blocking command and
hands control straight back to you — **the user never has to type "done"**.
Then you immediately call `secret-get`. Only when you genuinely have no
terminal on the user's machine do you fall back to asking them to run it.

Common triggers:
- Calling an external API (Brevo, Stripe, OpenAI, Anthropic, Hetzner, etc.)
- The user just generated a new token and wants you to use it once
- Authenticating to a CLI for which the existing session has expired
- Loading a secret into an env var for a subprocess

## Workflow

1. **Run the paste command yourself.** Pick a clear UPPER_SNAKE_CASE name and
   execute it as a **blocking foreground command** in the user's shell — e.g.
   `secret-paste BREVO_KEY`. Tell the user in one short line what you're
   asking for and that the dialog just opened:

   > "I need your Brevo API key for the campaigns endpoint — I've opened the
   > secret-paste dialog. Paste the value and click OK."

   **Critical — how to invoke it:**
   - Run it **in the foreground / blocking**. The command does not return
     until the user closes the dialog. That return *is* your signal to
     continue — **do not** ask the user to type "done", and **do not** make
     them confirm.
   - **Never** launch it detached/backgrounded (no `&`, no `Start-Process`,
     no `nohup`, no `run_in_background`). A detached launch returns
     immediately and breaks the auto-resume — that's the one thing to avoid.
   - Set a **generous timeout** (e.g. 5–10 min) so the user has time to find
     and paste the value before your tool call times out.

   Useful flags to add:
   - `--ttl=24` — keep in the persistent store for 24 hours (default)
   - `--persist` — keep permanently (use for keys you'll re-use across sessions)
   - `--desc="Brevo transactional API key"` — shows in the dialog as context

2. **The command returns when the user closes the dialog.** Check its output:
   `OK: <NAME> stored locally (...)` means success → continue. `Cancelled.`
   (exit 1) means the user dismissed it → ask whether to retry. No polling,
   no waiting for a chat message.

   *(Fallback only if you have no terminal on the user's machine: ask them to
   run `secret-paste BREVO_KEY` themselves, then continue once they confirm.)*

3. **Retrieve via `secret-get`.** Stdout will be one line:

   ```
   OK: BREVO_KEY available at <ABSOLUTE_PATH> (5min TTL, source=<backend>)
   ```

   Parse `<ABSOLUTE_PATH>` from that line — it is a **stable contract**.

4. **Read the value from the file**, not from stdout. Use it directly.
   **Never:**
   - print the value with `echo` / `print` / `Write-Host` / `cat`
   - pass it as a positional CLI argument (e.g. `curl -H "X-API-Key: <VALUE>"`)
   - put it in tool-call arguments as a literal string
   - mention the value's content in your reply to the user

   **Safe patterns:**
   - PowerShell: ``curl -H "api-key: $(Get-Content -Raw '<PATH>')" ...``
     or ``. (secret-get BREVO_KEY --export-env | Out-String | Invoke-Expression)``
   - POSIX shell: ``eval "$(secret-get BREVO_KEY --export-env)"`` then use ``$BREVO_KEY``
   - Python:
     ```python
     value = pathlib.Path(path).read_text(encoding="utf-8").strip()
     # use `value` only inside this process, never in shell argv
     ```

5. **When you're done with the key** within the conversation (e.g. the task
   is finished), you may suggest `secret-revoke KEY_NAME` to the user if
   the credential was one-shot. Otherwise the persistent-store TTL handles
   cleanup automatically.

## Listing / clean-up commands

- `secret-list` — show stored credential names, source, created, expires.
  Never returns values. Safe to call to check if a key is already loaded
  before asking the user to paste again.
- `secret-revoke KEY_NAME` — delete the stored credential locally.

## The two TTLs

There are two independent expiries — don't confuse them in your reply:

- **Persistent-store TTL** (`--ttl=24`, hours; or `--persist` for none) —
  how long the encrypted blob lives in DPAPI / keyring before `secret-get`
  refuses to return it.
- **Temp-file TTL** (always 5 minutes, not configurable) — how long the
  unencrypted handoff file at the path `secret-get` prints lives. The next
  `secret-paste` call sweeps expired files. POSIX mode `0600`.

## When NOT to use secret-paste

- Credentials already accessible: `$env:GITHUB_TOKEN`, `gh auth status`,
  `~/.aws/credentials`, a project `.env` you can `cat`. Use those directly.
- Credentials the user has explicitly already pasted into this chat. The
  damage is done; ask them to rotate, but you can use what you have for
  the current call.
- Long-lived secrets that belong in a real vault (1Password / Bitwarden /
  Vault). secret-paste is for **ad-hoc / freshly-issued / one-off** keys.

## If secret-paste isn't installed yet

If `secret-paste` is not on the user's `PATH`, install it:

```bash
pipx install secret-paste
secret-paste-install-skill   # refreshes this skill from the package
```

If `pipx` isn't available either, fall back to:

```bash
pip install --user secret-paste
```

Then ask the user to open a new terminal so `secret-paste` is on `PATH`.

## Reference

Repo: https://github.com/MoritzV42/secret-paste — MIT licensed, ~650 LOC,
no telemetry. Read `secret_paste_core.py` if you want to verify what the
tool does before recommending it.
