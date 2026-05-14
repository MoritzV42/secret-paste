# Launch copy

Cut-and-paste pitches for `secret-paste` v0.1. Each is sized for its venue.

---

## Show HN

**Title** (≤ 80 chars — current: 71):

```
Show HN: Secret-paste – feed AI agents secrets without leaking them to chat
```

**Body** (≤ 500 chars — current: 487):

```
When my coding agent asks for an API key, pasting it into chat means the
value lives in the transcript forever. secret-paste is a tiny CLI + GUI
dialog: the agent runs `secret-paste BREVO_KEY`, I paste the value into a
local dialog, then `secret-get BREVO_KEY` hands the agent a path to a
5-minute-TTL temp file. Value never touches the chat. Windows DPAPI / macOS
Keychain / Linux libsecret. MIT, ~650 LOC, no telemetry.
```

---

## r/ClaudeAI

**Title:**

```
I built a tiny tool so Claude can ask for API keys without me pasting them into chat
```

**Body:**

```
Every time Claude Code or my custom Anthropic-SDK agent needed an API key,
I had a choice: paste it into the chat (and watch it survive every retry
forever), or stop the agent, pre-register the secret in a vault, restart.

secret-paste is the smallest fix I could find. Workflow:

1. Claude asks: "I need your Brevo API key. Please run
   `secret-paste BREVO_KEY` in your terminal."
2. A local GUI dialog opens. I paste the value once. Click OK.
3. Claude calls `secret-get BREVO_KEY` itself. Receives a path to a
   5-minute-TTL temp file. Reads the value from the file, uses the API,
   moves on.

The agent's transcript never contains the value — just a path. The temp
file evaporates after 5 minutes. The persistent copy is DPAPI-encrypted on
Windows / in the Keychain on macOS / libsecret on Linux. MIT-licensed, 
~650 LOC, no telemetry, no remote calls.

I added a paste-able system-prompt blurb in the README so Claude reliably
asks for `secret-paste KEY_NAME` instead of trying to talk me into pasting
into chat.

Looking for Mac testers — the macOS Keychain backend is CI-green but I
don't own a Mac. Repo + install:
https://github.com/MoritzV42/secret-paste
```

---

## r/LocalLLaMA

**Title:**

```
Stop pasting API keys into your local-agent chat: a 650-LOC OS-keyring + GUI bridge
```

**Body:**

```
For folks running local agents (Ollama orchestrators, open-source-model
Cursor forks, llama.cpp tool-use setups), the prompt-injection / transcript
leak problem is the same as for cloud agents. Every secret you paste into
the conversation gets logged by your local conversation store, replayed on
every regen, and shipped to any cloud model you switch to mid-session.

secret-paste is platform-native and dependency-light:

* Backend: Windows DPAPI / macOS Keychain / Linux libsecret — whatever your
  OS already trusts. No new daemon, no Docker, no Rust toolchain.
* No network: every byte stays on the box.
* Plugin interface for self-hosted remote backends (sops/age planned for
  v0.2 for teams that want a portable file).
* MIT, pure Python (only deps: `pywin32` on Win, `keyring` on Mac/Linux).

Workflow: agent runs `secret-paste KEY_NAME`, you paste into a local Tk
dialog, agent reads via `secret-get KEY_NAME` which drops the value into a
5-min-TTL temp file and prints only the path. The value never enters the
chat or the model's context window.

Pre-commit gitleaks + ruff + pytest matrix on Win/Mac/Linux × Py 3.10-3.12
all green.

https://github.com/MoritzV42/secret-paste — feedback / Mac testers welcome.
```

---

## r/cursor

**Title:**

```
Stop pasting API keys into Cursor: tiny tool so the agent can request them out-of-band
```

**Body:**

```
If you've used Cursor's agent mode for any infrastructure work, you've hit
this: the agent needs a new Stripe / Brevo / Hetzner key, you paste it into
the chat, and now it's in the conversation forever — replayed on every
retry, in the .cursor / .specstory transcript on disk, in your sync.

secret-paste is a 650-LOC CLI + tk dialog that fixes this:

1. Add a one-paragraph rule to your `.cursor/rules` (or composer system
   prompt) telling Cursor to ask for `secret-paste KEY_NAME` instead of a
   chat paste. The exact blurb is in the README.
2. When Cursor asks, you run `secret-paste BREVO_KEY` in your integrated
   terminal — a local GUI dialog pops up. Paste the value, click OK.
3. Cursor calls `secret-get BREVO_KEY` itself. Gets a path to a 5-min-TTL
   temp file. Reads the value from the file. The agent's context window
   only ever sees the path, not the value.

Storage: Windows DPAPI / macOS Keychain / Linux libsecret. Install:
`pipx install secret-paste`. MIT.

https://github.com/MoritzV42/secret-paste
```

---

## Posting checklist

- [ ] Replace `BREVO_KEY` / `Brevo` references with whatever's most generic
      to the audience if it feels too specific.
- [ ] Title char counts: Show HN 71 / 80 used; subreddit titles fit each
      sub's 300-char limit.
- [ ] Show HN body is 487 chars (limit 500).
- [ ] Don't double-post within 24 hours.
- [ ] Pin r/cursor and r/ClaudeAI posts to the `Tools` / `Showcase` flair.
- [ ] After 1 hour, check comments — respond to first 5 within the first 4
      hours. Highest engagement window.
