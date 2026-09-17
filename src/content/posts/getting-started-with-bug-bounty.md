---
title: "Getting Started with Bug Bounty Hunting"
description: "A practical writeup about learning bug bounty hunting — picking programs, staying in scope, and building a repeatable process."
date: 2026-09-10
tags:
  - Bug Bounty
  - Web Security
  - Security
---

Most "how to start bug bounty" advice is a list of vulnerability classes. That
list is not the hard part. The hard part is doing the same careful thing a
hundred times without getting bored.

## Read the scope first, twice

Before any tooling runs, the scope document gets read end to end. In-scope
domains, out-of-scope domains, forbidden techniques, rate limits. Anything not
explicitly in scope is out of scope — not "probably fine".

I keep the scope in a file next to the notes so it is impossible to drift:

```text
programs/
└── example-corp/
    ├── scope.md          # copied verbatim from the program page
    ├── recon/
    └── findings/
```

## Recon that you can repeat tomorrow

Subdomain enumeration, resolve, probe, screenshot. Same order every time:

```bash
subfinder -d example.com -all -silent > recon/subs.txt
dnsx -l recon/subs.txt -silent -a -resp > recon/resolved.txt
httpx-toolkit -l recon/subs.txt -sc -title -tech-detect -o recon/live.txt
```

The output is worth diffing against last week's run. New hostnames are the
highest-signal thing in bug bounty, and they only show up if you kept the
previous file.

## Pick a class and go deep

Breadth finds duplicates. Depth finds the thing three other hunters walked
past. For a first month, access control is the most productive place to look:
it needs no exotic payloads, only two accounts and patience.

```http
GET /api/v2/orders/10482 HTTP/1.1
Host: app.example.com
Authorization: Bearer <account-B-token>
```

If account B reads account A's order, that is the whole finding. No encoding
tricks required.

## Write the report like the triager is tired

A good report is short and mechanical:

1. One sentence on impact.
2. Exact reproduction steps, with real requests and responses.
3. What an attacker gets, stated plainly.
4. No speculation about severity you cannot demonstrate.

If a finding looks low on its own, keep it anyway. Two low findings that chain
into account takeover are not two lows.

## What to skip at the start

- Automated scanners fired at everything. They produce noise and duplicates.
- Chasing the newest CVE. Everyone else is already there.
- Anything even slightly outside scope. It ends programs, not just reports.
