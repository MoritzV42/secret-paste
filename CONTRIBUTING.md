# Contributing

Thanks for considering a contribution! `secret-paste` is small on purpose — keep
PRs focused.

## Dev install

```bash
git clone https://github.com/MoritzV42/secret-paste
cd secret-paste
python -m venv .venv
# Windows
.\.venv\Scripts\Activate.ps1
# macOS / Linux
source .venv/bin/activate
pip install -e ".[dev]"
```

`pip install -e ".[dev]"` installs the package in editable mode plus the
test/lint extras (`pytest`, `ruff`, `black`). After install, the four entry
points (`secret-paste`, `secret-get`, `secret-list`, `secret-revoke`) are on
your `PATH`.

Run a script directly during development without an install:

```bash
python secret_paste_cli.py TEST_KEY --ttl=1   # persistent store kept 1 hour
python secret_get_cli.py TEST_KEY              # value drops to a 5-min-TTL temp file
python secret_list_cli.py
python secret_revoke_cli.py TEST_KEY
```

## Tests

```bash
pytest
```

Tests run on Win/macOS/Linux × Python 3.10–3.12 via the
`.github/workflows/test.yml` matrix.

## Linter

```bash
ruff check .
black --check .
```

Both run in CI (`.github/workflows/lint.yml`).

## Pre-commit (optional)

```bash
pip install pre-commit
pre-commit install
```

Runs `ruff` and `gitleaks` on every commit.

## Commit style

Conventional-ish: `feat:`, `fix:`, `docs:`, `refactor:`, `chore:`. Keep the
subject under ~72 chars. Body in English.

## Pull requests

- One concern per PR. Split unrelated changes.
- Describe the user-visible behavior change, not just the diff.
- If you add a new backend, implement the full `VaultBackend` interface in
  `secret_paste_core.py` and add it to the README compatibility section.
- Never commit a real secret. Use placeholders like `<paste your token>`.

## Code of conduct

Be kind. Assume good faith. No spam / harassment / off-topic threads.
