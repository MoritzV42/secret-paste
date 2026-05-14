# Contributing

Thanks for considering a contribution! `secret-paste` is small on purpose â€” keep
PRs focused.

## Dev install

```powershell
git clone https://github.com/MoritzV42/secret-paste
cd secret-paste
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Run a script directly during development:

```powershell
python .\secret-paste.py TEST_KEY --ttl=1
python .\secret-get.py TEST_KEY
python .\secret-list.py
python .\secret-revoke.py TEST_KEY
```

## Linter

Not yet wired up. Planned: `ruff` + `black`. See ROADMAP.

## Tests

Not yet wired up. Planned: `pytest` with cross-platform matrix in CI. See
ROADMAP.

## Commit style

Conventional-ish: `feat:`, `fix:`, `docs:`, `refactor:`, `chore:`. Keep the
subject under ~72 chars. Body in English.

## Pull requests

- One concern per PR. Split unrelated changes.
- Describe the user-visible behavior change, not just the diff.
- If you add a new backend, implement the full `VaultBackend` interface in
  `_common.py` and add it to the README compatibility section.
- Never commit a real secret. Use placeholders like `<paste your token>`.

## Code of conduct

Be kind. Assume good faith. No spam / harassment / off-topic threads.
