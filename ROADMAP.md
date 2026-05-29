# Roadmap

Tracked work for secret-paste.

## v1.0 — shipped 2026-05

- Cross-platform local backend: Windows DPAPI + macOS Keychain + Linux
  libsecret / kwallet (via `keyring`)
- `pipx install secret-paste` on all three OSes
- Machine-readable `secret-get` output: `--json` and `--print-path`
  (value never on stdout, only the temp-file path)
- OS dark-mode detection in the paste dialog (Windows / macOS / Linux)
- Optional, **write-only** remote mirror (off by default): feature flag
  (`--enable-remote` / `--disable-remote` / `--show-config`), backend config
  (`--set-remote sops-age --recipient ...`), file-based sops/age backend
  skeleton, vault detection, conditional mirror checkbox, fail-isolated writes
- AI-assisted setup (`SETUP.md`)
- pytest suite (100+ tests) + GitHub Actions matrix CI (Win/macOS/Linux ×
  Py 3.10–3.12), ruff + black + pre-commit + gitleaks
- `VaultBackend` plugin interface

## Next candidates

- **One-time secret sharing** (server-backed): upload a secret, share a
  single-view link that self-destructs after the first view. Needs an
  encrypting server backend so it stays trustworthy. Lets users *send* secrets,
  not just store them locally.
- Animated demo GIF in the README
- macOS / Linux human-tested confirmation (looking for testers)
- sops/age round-trip hardening + recipient provisioning in the GUI
- Bitwarden (`bw`) / 1Password (`op`) / HashiCorp Vault remote backends
- Optional system-tray icon as an alternative to the modal dialog
- Plugin auto-discovery (`secret_paste.backends` entry-point group)
