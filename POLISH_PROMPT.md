# Polish-Prompt for next Claude session

Copy-paste this entire file into a new Claude Code chat. The chat will polish
secret-paste from "extracted skeleton" to "public-release-ready" in one session.

## Context

You are polishing the `secret-paste` repo at `C:\GitHub\secret-paste\` for public
GitHub release. The skeleton is already done (extraction from InfinitySpace42
mono-repo, README, LICENSE, plugin interface stub). Your job: the remaining
~20h of polish work.

## Goals (prioritized)

### Must-have for v0.1 public release

1. **Cross-platform support**
   - macOS Keychain backend via `keyring` library
   - Linux libsecret backend via `keyring`
   - tkinter GUI must render correctly on all 3 platforms (Windows/macOS/Linux)
   - Test on at least 2 platforms (request Moritz to run on his Mac if he has one)

2. **pytest suite** â€” minimum coverage:
   - `_safe_name()` path-traversal protection
   - TTL expiry logic
   - Temp-file cleanup
   - DPAPI roundtrip (mocked)
   - VaultBackend interface contract test

3. **README polish**
   - Add animated GIF showing the paste-dialog flow (use asciinema or peek)
   - English copy review (have a sub-agent review)
   - Add "Why I built this" section linking to the original problem
   - Comparison table accuracy check (have sub-agent verify 1Password/Bitwarden claims)

4. **CI via GitHub Actions**
   - `.github/workflows/test.yml` â€” pytest on Win/Mac/Linux matrix
   - `.github/workflows/lint.yml` â€” ruff + black

5. **UX modernization**
   - tkinter default look is dated (1998-Windows). Apply ttk themes or sv-ttk for modern look
   - Better fonts, padding, error states
   - Show success-toast after paste

### Nice-to-have for v0.1

6. **pipx install support** (instead of PowerShell-only `install.ps1`)
7. **Pre-commit hook** that runs ruff + checks for committed secrets (use detect-secrets or gitleaks)
8. **Plugin: at least one remote backend implemented**
   - Recommend: Bitwarden (open-source, free tier, popular)
   - OR: file-based encrypted backend (age/sops) for self-hosted users
9. **Versioning + CHANGELOG.md**

### Out of scope for v0.1

- Web UI
- Multi-user sharing
- Enterprise compliance features
- Mobile clients

## How to work

- You may spawn sub-agents (general-purpose, Explore, Plan) for:
  - Code review after each major change
  - Cross-platform testing strategy
  - README copy review
  - Comparison-table fact-checking against 1Password/Bitwarden/Infisical docs
- Run pytest after every significant change â€” fail loud, don't sweep under rug
- Open PRs against `main` branch (or commit directly if Moritz approves direct-commit)
- Ask Moritz when you need: device access (e.g. "can you run this on your Mac?"), naming decisions, accepting tradeoffs (e.g. "Bitwarden backend or sops backend first?")
- DO NOT push to GitHub. Stage commits locally. Moritz reviews + pushes manually.

## When you think you're done

1. Run full pytest suite â€” must pass
2. Run README through a sub-agent posing as "first-time user trying to install in 60 seconds" â€” fix anything they stumble on
3. Generate the Show-HN pitch and Reddit pitches (in `MARKETING.md`):
   - Show HN title (max 80 chars) + body (max 500 chars)
   - r/ClaudeAI body
   - r/LocalLLaMA body
   - r/cursor body
4. Report back to Moritz: what's done, what's left, time spent, ready-to-launch checklist

Estimated wall-clock: 6-8h of agent work with sub-agents in parallel.
Moritz' time investment: ~30 minutes for Q&A.
