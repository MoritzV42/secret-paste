# secret-paste

> Give AI agents secrets without leaking them into your chat transcript.

When you copy-paste a token into Claude / Cursor / ChatGPT, it lives in the conversation forever.
`secret-paste` opens a local GUI dialog instead â€” you paste the secret there, the agent retrieves
it via `secret-get` (which never echoes the value to stdout).

## Quickstart (Windows)

```powershell
git clone https://github.com/MoritzV42/secret-paste
cd secret-paste
.\install.ps1
```

## Usage

1. Agent prompts: "I need your Brevo API key. Run `secret-paste BREVO_KEY` and paste it there."
2. You run it. GUI opens. Paste the value. Click OK.
3. Agent calls `secret-get BREVO_KEY` â€” receives only a path to a 5-minute-TTL temp file. Value never appears in chat.

## How it differs from existing tools

| Tool | Solves "AI never sees secret" | Ad-hoc paste (no pre-loaded vault) |
|---|---|---|
| 1Password `op run` / Bitwarden `bws run` | Yes | No â€” secret must already be in vault |
| Anthropic Managed Agents Vaults | Yes | No â€” pre-registered via REST API |
| Infisical Agent Vault | Yes (HTTPS proxy) | No |
| **secret-paste** | Yes | Yes â€” you paste a token you just got from Stripe / Brevo / etc. |

## Security

- DPAPI-encrypted at rest, user-scoped
- Temp file with 5-minute TTL, auto-cleanup
- Value never appears on stdout or in tool-arg strings
- MIT License â€” audit before use in production

## Status

- Windows (DPAPI) â€” supported
- Linux/Mac (keyring) â€” planned, see ROADMAP
- Remote backends (Bitwarden, 1Password, SSH-vault) â€” plugin interface in place, no implementation shipped yet
