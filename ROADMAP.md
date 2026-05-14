# Roadmap

Tracked work toward a stable v1.0 release.

## v0.1 — shipped 2026-05

- Cross-platform local backend: Windows DPAPI + macOS Keychain + Linux
  libsecret / kwallet (via `keyring`)
- `pipx install secret-paste` on all three OSes
- pytest suite (53 tests) + GitHub Actions matrix CI (Win/macOS/Linux ×
  Py 3.10–3.12)
- ruff + black + pre-commit + gitleaks
- VaultBackend plugin interface

## v0.2 candidates

- First remote backend (likely **sops + age**, file-based and self-hosted)
- Animated demo GIF in README
- macOS / Linux human-tested confirmation (looking for testers)
- `--json` / `--print-path` machine-readable output for `secret-get`
- Optional system-tray icon as an alternative to the modal dialog

## v0.3+ candidates

- Bitwarden remote backend (`bw` CLI)
- 1Password remote backend (`op` CLI)
- HashiCorp Vault remote backend
- Mirror-to-remote checkbox in the GUI (currently disabled)
- Plugin auto-discovery (`secret_paste.backends` entry-point group)
