# secret-paste

> Give AI agents secrets without leaking them into your chat transcript.

When you paste a token into Claude / Cursor / ChatGPT / your CLI agent, it
lives in the conversation forever — replayed on every retry, indexed in any
logs the provider keeps, visible to anyone who later loads the session.
`secret-paste` fixes this with the smallest possible primitive: a **local GUI
dialog** the agent asks you to open, plus a **5-minute-TTL temp file** the
agent reads from. The value never touches the chat.

```text
+----------------- Agent says -------------------------+
| "I need your Brevo API key. Run                      |
|   secret-paste BREVO_KEY                             |
|  and paste the value into the dialog that pops up."  |
+------------------------------------------------------+
                         |
                         v   (you run it locally)
+----------------- secret-paste BREVO_KEY -------------+
| Enter credential: BREVO_KEY                          |
| [ ******************************************** ]    |
| [ ] Show value                                       |
| Backend: Windows DPAPI                               |
|                                  [ Cancel ]  [ OK ]  |
+------------------------------------------------------+
                         |
                         v   (agent retrieves it)
  $ secret-get BREVO_KEY
  OK: BREVO_KEY available at C:\Temp\secret-paste-tmp\BREVO_KEY.val
      (5min TTL, source=Windows DPAPI)
```

The agent now has a **file path**, not a value, in its transcript. It reads
the file, uses the credential, and 5 minutes later the file is auto-deleted.

## Install

### With `pipx` (recommended — all OSes)

```bash
pipx install secret-paste
secret-paste-install-skill        # one-time: teach Claude Code to use it
```

You now have `secret-paste`, `secret-get`, `secret-list`, and `secret-revoke`
on `PATH` on Windows, macOS, and Linux. The second command drops a
[Claude-Code skill](#claude-code-integration) into `~/.claude/skills/` so
any Claude session on this machine automatically uses secret-paste instead
of asking you to paste credentials into chat.

Optional — for the modern UI (CustomTkinter, crisp on HighDPI + a polished
dark theme):

```bash
pipx install secret-paste[gui]
```

This is purely optional. Without it, `secret-paste` uses a zero-dependency
stdlib (tkinter) dialog that is DPI-aware and dark-mode-correct on its own.

### From source

```bash
git clone https://github.com/MoritzV42/secret-paste
cd secret-paste
pip install -e .
```

### Windows-only PowerShell installer

If you don't want a Python install on `PATH`, the bundled installer (after
`git clone`) copies the scripts into `%USERPROFILE%\bin\secret-paste\` and
wires shell functions into your `$PROFILE`:

```powershell
.\install.ps1
```

## Usage

1. **Agent** prompts: _"I need your Brevo API key. Run `secret-paste
   BREVO_KEY` and paste it into the dialog."_
2. **You** run it. A GUI dialog opens. Paste the value. Click **OK**.
3. **Agent** calls `secret-get BREVO_KEY`. Receives a path to a
   5-minute-TTL temp file. **The value never appears in chat.**

### Two TTLs

There are two independent TTLs and they mean different things:

- **Persistent-store TTL** (`--ttl=24`, hours) — how long the encrypted
  credential lives on disk / in the keyring before `secret-get` refuses to
  return it. Default 24 hours. `--persist` disables this.
- **Temp-file TTL** (always 5 minutes, not configurable) — how long the
  unencrypted value lives at the path that `secret-get` prints. The file is
  auto-deleted on the next `secret-paste` call.

### Common flags

```bash
secret-paste BREVO_KEY --ttl=24            # store kept for 24 hours (default)
secret-paste BREVO_KEY --persist           # store permanently (no expiry)
secret-paste BREVO_KEY --desc="Brevo API key (transactional email)"

secret-get BREVO_KEY                        # drops value to a temp file (5-min TTL)
secret-get BREVO_KEY --export-env          # auto-detects PowerShell or POSIX
secret-get BREVO_KEY --print-path          # prints ONLY the temp-file path
secret-get BREVO_KEY --json                # {"name","path","ttl_remaining"} (no value)

secret-list                                 # names + meta, NEVER values
secret-revoke BREVO_KEY                     # delete locally
```

## Claude-Code integration

If you use [Claude Code](https://claude.com/claude-code), the package ships
a skill file that makes Claude **auto-use** secret-paste whenever it needs
a credential — no system-prompt edit required. Install once:

```bash
secret-paste-install-skill
```

This copies `secret-paste.md` to `~/.claude/skills/`. Open a new Claude-Code
session and every future credential request will be routed through the
dialog automatically. To remove:

```bash
secret-paste-install-skill --uninstall
```

The Windows PowerShell installer (`install.ps1`) does this step for you.

### Tell other agents about it (Cursor / custom Anthropic-SDK / etc.)

For agents without a skill loader, drop this into your agent's system prompt /
`CLAUDE.md` / Cursor rules / custom-instructions file:

> When you need a credential that I haven't given you yet, do **not** ask me
> to paste it into the chat. Instead, ask me to run
> `secret-paste <KEY_NAME>` in my terminal, wait for me to confirm, then
> call `secret-get <KEY_NAME>` yourself. That prints a file path to a
> 5-minute-TTL temp file — read the value from that file (not from this
> chat) and use it directly. Never echo the value back to me.

The first line of `secret-get`'s stdout has a stable contract:

```
OK: <name> available at <absolute-path> (5min TTL, source=<backend>)
```

Agents can parse `<absolute-path>` from this line and read the file.

### Reading from agent code

PowerShell:

```powershell
. (secret-get BREVO_KEY --export-env | Out-String | Invoke-Expression)
curl -H "api-key: $env:BREVO_KEY" https://api.brevo.com/v3/account
```

POSIX shell (bash / zsh):

```bash
eval "$(secret-get BREVO_KEY --export-env)"
curl -H "api-key: $BREVO_KEY" https://api.brevo.com/v3/account
```

Python (robust — no regex parsing of the human-readable line):

```python
import subprocess, pathlib
path = subprocess.run(
    ["secret-get", "BREVO_KEY", "--print-path"],
    capture_output=True, text=True, check=True,
).stdout.strip()
value = pathlib.Path(path).read_text(encoding="utf-8").strip()
```

Or if you also want the remaining TTL, use `--json`:

```python
import subprocess, json, pathlib
info = json.loads(subprocess.run(
    ["secret-get", "BREVO_KEY", "--json"],
    capture_output=True, text=True, check=True,
).stdout)
# info == {"name": "BREVO_KEY", "path": "/.../BREVO_KEY.val", "ttl_remaining": 299}
value = pathlib.Path(info["path"]).read_text(encoding="utf-8").strip()
```

> `--json` / `--print-path` never put the value on stdout — only the path to the
> 5-minute-TTL temp file. The value still lives only in that file.

## Why I built this

I work with AI coding agents (Claude Code, Cursor, custom Anthropic-SDK
agents) on infrastructure where the agent regularly needs short-lived API
keys it's never seen before — a new Brevo transactional key, a Hetzner API
token, a one-off `gcloud` access token. Every time the agent asked me to
paste it into the chat, I had to either:

1. **Paste it** — and then revoke + rotate as soon as the work was done,
   because the value lived in the transcript and any retry would replay it.
2. **Manually pre-load it into a long-lived vault** and re-prompt the agent
   to pull it from there.

Both are friction. The first leaks. The second forces me to treat every
ad-hoc credential like a long-lived one.

`secret-paste` is the minimum primitive that fixes this: the agent points at
a key by name, I paste once into a local dialog, the agent reads the value
out-of-band, and the temp file evaporates in 5 minutes.

## How it differs from existing tools

The market for AI-agent credentials is converging on **pre-registered
vaults**: register every secret ahead of time, then let the agent reference
it. That works great for stable, long-lived credentials. It does **not**
work for the freshly-issued one-off token you got from Stripe 30 seconds
ago. `secret-paste` is the complementary primitive for that case.

| Tool | Hides value from AI transcript | Works for an ad-hoc / freshly-issued secret |
| --- | --- | --- |
| [1Password `op run`](https://developer.1password.com/docs/cli/secret-references/) | Yes (env-var injection) | No — must exist in a 1Password vault |
| [Bitwarden `bws run`](https://bitwarden.com/help/secrets-manager-cli/) | Yes (env-var injection) | No — must be created in Bitwarden Secrets Manager |
| [HashiCorp Vault](https://developer.hashicorp.com/vault/docs/commands/read) (+ agent) | Yes | No — secret must be written first |
| [Anthropic Managed Agents — Vaults](https://platform.claude.com/docs/en/managed-agents/vaults) | Yes | No — registered via REST API / console |
| [Infisical Agent Vault](https://github.com/Infisical/agent-vault) | Yes (HTTP proxy) | No — pre-registered in Infisical |
| [`pass`](https://www.passwordstore.org/) | Partial (terminal, GPG) | No GUI; persists indefinitely once written |
| **secret-paste** | Yes | **Yes** — local GUI dialog, no vault to pre-load |

The win isn't "another secrets manager" — it's the ad-hoc-paste-dialog
primitive that none of the above ship, plus a 5-minute-TTL handoff that
keeps the value out of the agent's context window. Pair it with whichever
vault you already use for long-lived credentials.

## Security model

- **At rest**: DPAPI-encrypted blob (Windows) or OS keyring entry (macOS
  Keychain, Linux libsecret / kwallet / KeePassXC) — user-scoped, never
  group-readable.
- **In transit to the agent**: temp file with 5-minute TTL, auto-cleanup on
  every `secret-paste` invocation, plus orphan sweep for files whose marker
  was lost. POSIX mode `0600`; dir is per-UID under `$XDG_RUNTIME_DIR` when
  available, with mode `0700`.
- **Never on stdout**: `secret-get` prints the path, not the value. The
  `--export-env` snippet reads the file inside the shell, not via `argv`.
- **Never in argv**: there is no `secret-set BREVO_KEY <value>` command —
  the value enters only via the dialog.
- **Opportunistic expiry**: when `secret-get` is called on an expired key,
  the DPAPI blob / keyring entry is purged on the spot so an attacker who
  later steals the blob cannot decrypt it.
- **MIT-licensed** — audit before use in production. ~650 lines of Python,
  ~200 of which is the dialog. No third-party crypto.

### Threats not covered by v0.1

- A compromised local user account can still read the keyring / DPAPI blob.
  `secret-paste` is not a substitute for full-disk encryption or hardware
  tokens.
- A logger that captures every file your shell writes will catch the temp
  file. If you have one, configure it to exclude
  `secret-paste-tmp/`.
- The dialog uses tkinter — if your display server forwards keystrokes to
  other clients, your paste is exposed. Same caveat as any other GUI
  password prompt.
- A shell with tracing enabled (`set -x`, `Set-PSDebug -Trace`) will echo
  the expansion of the `--export-env` snippet. Run it untraced.

## Platforms

| OS | Backend | Status |
| --- | --- | --- |
| Windows 10 / 11 | DPAPI (`pywin32`) | Supported — author's daily driver |
| macOS 13+ | Keychain (`keyring`) | CI-green on `macos-latest`; Mac testers wanted — open an issue with feedback. |
| Linux (GNOME / KDE) | libsecret / kwallet / KeePassXC (`keyring`) | CI-tested on `ubuntu-latest`. Needs a Secret Service provider running. |

## Roadmap

- macOS / Linux human-tested confirmation
- First remote backend (likely `sops` + `age`, file-based and self-hosted)
- Bitwarden / 1Password remote-mirror backends
- Animated demo GIF in this README

See [`ROADMAP.md`](ROADMAP.md) for the full list and [`CHANGELOG.md`](CHANGELOG.md)
for release notes.

## Contributing

PRs welcome. See [`CONTRIBUTING.md`](CONTRIBUTING.md) for dev setup, test
matrix, and the `VaultBackend` plugin contract.

## Recording the demo GIF

If you want to send a recording for the README:

```bash
# macOS / Linux
asciinema rec demo.cast
secret-paste DEMO_KEY --ttl=1
secret-get DEMO_KEY
exit
# Convert to GIF with https://github.com/asciinema/agg
agg demo.cast demo.gif

# Windows: the GUI dialog isn't captured by asciinema.
# Use ShareX or Peek for the dialog flow.
```

Open an issue with the file attached.


<!-- PORTFOLIO-LINKS:START -->
## More open-source tools by Moritz Voigt

- **[secret-paste](https://github.com/MoritzV42/secret-paste)** — Paste API keys & tokens to your AI coding agent without ever putting them in the chat transcript. Local-only, cross-platform. *(this repo)*
- **[push-to-clip](https://github.com/MoritzV42/push-to-clip)** — Copy text, files, or piped output to your system clipboard, from one command, on any OS.
- **[memoryball-studio](https://github.com/MoritzV42/memoryball-studio)** — Batch-prep a whole photo folder for the Memory Orb display ball: auto-cropped, face-aware, the right format — locally.
- **[ingpad](https://github.com/MoritzV42/ingpad)** — The engineer's scratch pad: solve technical exercises on one canvas with per-step Given / Sought / Approach, stylus fields, and an AI tutor.

All MIT-licensed, free, built in public → **[moritzvoigt.infinityspace42.de](https://moritzvoigt.infinityspace42.de)**
<!-- PORTFOLIO-LINKS:END -->

## License

[MIT](LICENSE) (c) Moritz Voigt
