# One-time secret sharing — design concept

> **Status: design + skeleton only.** Nothing in this document is wired into a
> default code path yet. The `--share` flag stubs out to "not yet implemented".
> This file exists so the server approach can be chosen deliberately before any
> server is built. See the [open decisions](#open-decisions-for-the-maintainer)
> checklist at the bottom — those gate implementation.

## What it is

Today `secret-paste` only *stores* a credential locally so an AI agent on the
same machine can read it out-of-band. It cannot *send* a secret to another
person.

One-time sharing adds exactly that, in the
[onetimesecret](https://onetimesecret.com/) style: you upload a secret, get back
a single-view URL, and hand that URL to someone. The first time anyone opens it,
the secret is revealed **and immediately destroyed** server-side. A second visit
shows nothing. This bounds the exposure window: a link that has been viewed is
provably spent, and a link that was intercepted but already opened by the
recipient is detectably burned (the recipient sees "already viewed").

```text
  secret-paste --share DB_PASSWORD
        |
        v   (client encrypts locally, uploads only ciphertext)
  https://share.example.com/s/AbC123#k=<base64url-key>
        |                              \_______________/
        |                               key lives ONLY in the URL fragment
        v   (recipient opens once)
  reveals plaintext  ->  server deletes the ciphertext  ->  link is now dead
```

## Threat model + trust requirement

The whole point of `secret-paste` is *not* trusting a transcript or a log with a
plaintext secret. A naive "upload secret to a server, server hands it out once"
design throws that away — now the **server** sees every plaintext and becomes the
single juiciest target. That is unacceptable for this tool.

**Hard requirement: the server must be zero-knowledge.** It stores only
ciphertext and never possesses the decryption key.

| Party | Sees | Must NOT see |
| --- | --- | --- |
| Sender (client) | plaintext, key, ciphertext | — |
| Server | ciphertext, opaque record id, TTL, view-count | plaintext, key |
| Recipient (client) | ciphertext (fetched), key (from URL fragment), plaintext (decrypted locally) | — |
| Network observer / log | record id, ciphertext in transit (over TLS) | plaintext, key |

How the key stays off the server:

- The decryption key is encoded into the URL **fragment** (`#k=...`). Per
  [RFC 3986 §3.5](https://www.rfc-editor.org/rfc/rfc3986#section-3.5), the
  fragment is **never sent to the server** in an HTTP request — browsers and
  HTTP clients strip everything after `#` before transmitting. So the server
  receives `GET /s/AbC123`, never the `#k=...` part.
- The recipient's client (a browser page served by the server, or
  `secret-paste --open <url>`) reads the fragment locally, fetches the
  ciphertext by id, decrypts in memory, and shows the plaintext. Decryption
  happens entirely client-side.

Residual risks (must be documented for users, not "solved"):

- A **malicious or compromised server** could serve a tampered JS page that
  exfiltrates the key after the recipient's browser reads the fragment. This is
  the classic "trust the JS you're served" problem of all web-based E2E tools.
  Mitigations: self-host the server; prefer the CLI `--open` path (no served JS
  to trust); publish the page as a static, hash-pinned asset. **This is a real
  limitation, not eliminable for the browser flow.**
- **Metadata leak**: the server learns when a secret was created, its size
  (pad to bucket sizes to blunt this), and when/whether it was viewed.
- **Fragment in history**: the full URL (with key) lands in the recipient's
  browser history / clipboard managers. One-time-view limits the damage but does
  not erase the local copy. Document it.
- **TLS interception** at the recipient: out of scope (same caveat as any HTTPS
  tool).

## Proposed UX

Sending (new, opt-in flag — never the default):

```bash
secret-paste --share DB_PASSWORD
# -> opens the same paste dialog (value never on argv),
#    encrypts locally, uploads ciphertext, prints:
#
#    One-time link (self-destructs after first view, expires in 24h):
#      https://share.example.com/s/AbC123#k=Zk9...base64url
#
#    The recipient sees the secret exactly once. The key after '#' is
#    never sent to the server — keep the whole URL together.
```

Variants worth supporting later (all behind the same flag family):

```bash
secret-paste --share DB_PASSWORD --share-ttl=1h   # server-side expiry if unopened
echo "$TOKEN" | secret-paste --share-stdin API_KEY  # pipe-friendly (still no argv value)
secret-paste --open "https://share.example.com/s/AbC123#k=..."  # CLI recipient, no browser
```

The reveal path is one of:

1. **Browser** — recipient opens the URL; the server returns a minimal page that
   reads the fragment, fetches `GET /s/<id>` (which atomically deletes), and
   decrypts in-page.
2. **CLI** — `secret-paste --open <url>` does the same fetch+decrypt without any
   served JS to trust (preferred for the security-conscious).

## How it fits the backend interface

The existing `VaultBackend` ABC (`put` / `get` / `delete` / `list`,
`supports_read`, the `backend_get` choke point) models *named, re-readable*
credential storage. One-time sharing is a **different shape**:

- It is **write-then-read-once-then-gone**, not stable named storage.
- It returns a **share artifact** (URL + key), not a stored-under-name handle.
- `get` is not idempotent — reading destroys. That violates the implicit
  contract callers assume from `VaultBackend.get` (safe to call, returns the
  same value, routed through `backend_get`).

Forcing it into `VaultBackend` would either break that contract or require ugly
special-casing in `backend_get`. So the recommendation is a **separate,
parallel `ShareBackend` concept** that does not inherit from `VaultBackend`.

Proposed method shape (concrete — see the skeleton in
`secret_paste_core.py`):

```python
@dataclass
class ShareLink:
    """Result of creating a one-time share. Carries NO plaintext."""
    url: str          # full link incl. '#k=...' fragment, ready to hand over
    record_id: str    # opaque server id (the part the server sees)
    expires_at: str | None = None  # ISO-8601 server-side expiry if unopened

class ShareBackend(ABC):
    name: str = "abstract-share"

    @abstractmethod
    def create(self, value: str, *, ttl_seconds: int | None = None) -> ShareLink:
        """Encrypt ``value`` client-side, upload only ciphertext, return a
        one-time link. The plaintext and key never leave the client except
        inside the returned URL's fragment."""

    @abstractmethod
    def reveal(self, url: str) -> str:
        """Fetch + decrypt the secret behind ``url`` exactly once. The server
        destroys its copy as part of serving the read. Raises if already
        viewed / expired / not found."""
```

Why not reuse `put`/`get`: the signatures differ (no `name`; `create` returns a
`ShareLink`; `reveal` takes a URL and is destructive). Keeping the two interfaces
separate keeps `VaultBackend`'s "safe, named, idempotent read" guarantee intact
and makes the destructive semantics explicit in the type.

The two interfaces *can* share helpers (the `age`/sealed-box crypto, `_safe_name`
sanitizing) at the module level.

## Server options compared

| Option | Zero-knowledge? | Self-host effort | Ongoing cost | Notes |
| --- | --- | --- | --- | --- |
| **Cloudflare Worker + Workers KV** (TTL on keys) | Yes — stores ciphertext blob keyed by random id, KV native per-key TTL, atomic delete-on-read | Low (one `wrangler deploy`) | Free tier covers hobby volume | Recommended. No server to patch, global edge, KV TTL gives "expire if unopened" for free. Atomic single-view via read-then-delete (KV is eventually-consistent — see decision below). |
| **Tiny self-hosted FastAPI + SQLite/Redis** | Yes (same client-side crypto) | Medium (host, TLS, process mgmt) | A small VPS | Full control, easy to audit (~100 lines). Single-view delete is trivially atomic in SQLite (`DELETE ... RETURNING`). More to operate. |
| **Integrate an existing onetimesecret instance** (self-host or SaaS) | Their server holds the secret keyed by a passphrase — **not** fragment-key zero-knowledge by default | Low–medium | Free (self-host) / paid (SaaS) | Battle-tested UX, but the trust model differs (server can see plaintext unless you layer our client-side crypto on top, which fights their design). Not recommended as the primary backend. |

**Recommendation: Cloudflare Worker + Workers KV.** It matches the project's
existing hosting (the landing page is already on Cloudflare Pages), needs no
server to maintain, gives per-record TTL natively, and is cheap-to-free at this
scale. The FastAPI option is the fallback if strict read-then-delete atomicity
turns out to matter more than operational simplicity (KV's eventual consistency
means a race could in theory allow a second read in a tiny window — a SQLite
`DELETE ... RETURNING` closes that). Keep the `ShareBackend` interface so both
can coexist and the choice is config, not code.

## Crypto choice

Two viable primitives, both put the key in the URL fragment as base64url:

1. **age / X25519** (`age` is already a known CLI in this repo —
   `KNOWN_VAULT_CLIS`). Generate an ephemeral X25519 identity per share;
   encrypt the plaintext to its recipient; the URL fragment carries the
   **identity (private) key**; the server stores the age ciphertext. Pro: reuses
   the existing `age` dependency story and the `SopsAgeBackend` mental model.
   Con: shelling out to `age` for a per-share ephemeral key is clumsy.

2. **libsodium sealed box / secretbox** (via [PyNaCl](https://pynacl.readthedocs.io/)).
   Generate a random 32-byte symmetric key client-side, `crypto_secretbox` the
   plaintext (XSalsa20-Poly1305), upload the ciphertext+nonce, put the symmetric
   key in the fragment as base64url. Decryption is symmetric and trivial in both
   the CLI and a browser (libsodium.js). Pro: clean, no subprocess, one small
   dependency, identical primitive client+server-less. **Recommended.**

Fragment format proposal: `#k=<base64url(32-byte key)>` (and the nonce travels
with the ciphertext on the server, since it is not secret). base64url (no
padding) keeps the URL clean and copy-paste-safe.

Crypto is an **optional extra** (`secret-paste[share]` pulls PyNaCl), so the
core tool stays dependency-light and the local-only flow is untouched.

## Packaging

Strong lean: ship this as a **separate optional extra**, not in the always-loaded
core path. The local-only tool is the proven, dependency-light primitive; sending
secrets over a network is a categorically larger surface (a server, a crypto dep,
a hosted domain, abuse handling). Options:

- `pip install secret-paste[share]` — same package, extra dependency group,
  `ShareBackend` lives in core but only imports PyNaCl lazily. (Simplest for
  users; recommended.)
- A separate `secret-paste-share` package/repo. (Cleanest separation; more
  release overhead.) **Open decision below.**

## Open decisions for the maintainer

Implementation should not start until these are settled:

- [ ] **Server approach**: Cloudflare Worker + KV (recommended) vs. self-hosted
      FastAPI vs. existing onetimesecret. Decides atomicity guarantees + ops.
- [ ] **Hosting + domain**: where does the server live and under what hostname?
      (e.g. `share.infinityspace42.de`?) Affects DNS, TLS, the printed URL, and
      whether it sits behind the existing Cloudflare tunnel.
- [ ] **Retention / TTL policy**: default server-side expiry-if-unopened (24h?
      7d?), max allowed TTL, and whether the sender can override per-share.
- [ ] **Single-view atomicity**: is KV's eventual consistency acceptable, or is
      a strongly-consistent store (SQLite `DELETE ... RETURNING`, Durable Object)
      required to guarantee exactly-once reveal?
- [ ] **Rate-limiting + abuse**: per-IP create limits, max ciphertext size,
      CAPTCHA / token to prevent the endpoint becoming a free anonymous file
      drop or spam relay. Who pays if it gets abused?
- [ ] **Crypto primitive**: libsodium/PyNaCl sealed box (recommended) vs.
      age/X25519. Decides the dependency and the fragment format.
- [ ] **Packaging**: `secret-paste[share]` extra (recommended) vs. a separate
      `secret-paste-share` package. Decides the release + dependency story.
- [ ] **Reveal UX**: ship a browser reveal page (must trust served JS) and/or
      a CLI `--open` path (no served JS) — and which is the documented default.
- [ ] **Logging / metadata**: confirm the server logs **zero** plaintext and
      decide what metadata (size, timestamps, view-count) is acceptable to keep.
- [ ] **Legal / ToS**: a hosted endpoint that relays arbitrary user data needs
      an abuse contact + a short ToS. Confirm before going public.

## Non-goals (for this first concept)

- Multi-view links, password-on-top-of-fragment, recipient authentication,
  read receipts/notifications — all deferrable until the core single-view flow
  is chosen and shipped.
- Replacing the local-only flow. One-time sharing is **additive and opt-in**;
  the existing commands keep working with zero new dependencies.
