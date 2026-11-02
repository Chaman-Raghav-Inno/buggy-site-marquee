# buggy-site-marquee: Marquee

Marquee is a demo event ticketing site (concerts, theatre, comedy and sport: listings, event pages with ticket types
and seat maps, a basket with timed holds, promo codes, checkout, my tickets with transfers, resale and refunds,
waitlists, and an organiser dashboard) with **40 functional bugs planted on purpose**, to measure how many the AI QA
Scanner finds. It is the seventh benchmark site, after
[buggy-site](https://github.com/Chaman-Raghav-Inno/buggy-site) (Lumen Goods),
[buggy-site-taskline](https://github.com/Chaman-Raghav-Inno/buggy-site-taskline) (Taskline),
[buggy-site-driftwood](https://github.com/Chaman-Raghav-Inno/buggy-site-driftwood) (Driftwood Stays),
[buggy-site-fernhill](https://github.com/Chaman-Raghav-Inno/buggy-site-fernhill) (Fernhill Academy),
[buggy-site-kestrel](https://github.com/Chaman-Raghav-Inno/buggy-site-kestrel) (Kestrel Works) and
[buggy-site-copperleaf](https://github.com/Chaman-Raghav-Inno/buggy-site-copperleaf) (Copperleaf Bank). Its bugs
break ticketing rules: capacity and overselling, hold expiry, per-order and per-account limits, seat-map rules, early
bird dates and venue time zones, fee arithmetic, promo codes, refund windows, transfers and resale, waitlists,
permissions, and the organiser's prices, releases, cancellations, attendee list and check-in.

The events and venues are fictional, and it says on every page that there are no real tickets or payments.

[BUGS.md](BUGS.md) is the answer key: for each bug, the steps to reproduce, what should happen, what happens, its
severity, how hard it is to notice and where it is in the code. The site never serves that file, and nothing it
serves names or hints at a bug. The rules each bug breaks are published on the site (`/help`).

## Run it

```sh
python -m marquee          # http://localhost:8088 (PORT changes the port)
```

Standard library only (Python 3.11+); no install step.

- Accounts (password `Marquee@2026`, shown on the login page): `zoe@marquee.test` (fan),
  `max@marquee.test` (organiser of eight events).
- Every visitor (cookie) gets a private copy of the demo world, dated around today, so parallel scans never see each
  other's changes. Both accounts share that copy within one browser. A restart or redeploy resets everything.
- Checkout is a demo: use the test card `4242 4242 4242 4242` with any future expiry date.

## Deploy on Railway

New service → GitHub repo → this repository, then **Generate domain** under Networking. `railway.json` sets the
start command and health check (`/healthz`); no variables or volume are needed. Avoid redeploying while a scan runs.

## Development

```sh
pip install ruff pytest
ruff check . && ruff format --check .
pytest -q
```

`tests/test_marquee.py` keeps the server-side bugs in place and checks that nothing served gives a bug away.
Server-side code marks each bug with a `BUG-nn` comment; the served files must not.
