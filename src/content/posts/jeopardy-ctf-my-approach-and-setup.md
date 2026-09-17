---
title: "Jeopardy CTF — My Approach and Setup"
description: "How I approached a Jeopardy-style CTF, what tools I used, and how I organized my workflow."
date: 2026-09-15
tags:
  - CTF
  - Cybersecurity
  - Methodology
image: ../../assets/images/ctf-terminal-setup.png
imageAlt: "A terminal showing an nmap service scan followed by an ffuf content discovery run"
---

Jeopardy CTFs reward preparation more than cleverness. The teams that finish
well are usually the ones who never lose ten minutes to "where did I save that
output again?" This is the setup I keep coming back to.

## Recon

The first pass is always the same, and it is always scripted. One command,
one directory per target, everything on disk:

```bash
nmap -sV -p- --min-rate 2000 -oA scans/initial target.example.com
```

Once the service list is in, content discovery runs against anything that
speaks HTTP:

```bash
ffuf -u http://target.example.com:8080/FUZZ \
     -w ~/wordlists/custom-target.txt \
     -mc 200,301,403 \
     -o scans/ffuf-8080.json
```

The generic wordlist gets me started. The list that actually finds things is
the one I build during the event, from words the target itself uses.

## Challenge 1 — a web app that trusted its own headers

The application decided who you were from an `X-Forwarded-User` header that a
front-end proxy was supposed to strip. It did not strip it.

```http
GET /admin/export HTTP/1.1
Host: target.example.com
X-Forwarded-User: admin
```

That returned the export endpoint's full response. The interesting part was
not the bug — it was that I only noticed the header because I had the proxy
history open in a second window, diffing an authenticated request against an
anonymous one.

## Challenge 2 — a forensics image with a familiar shape

A disk image, a deleted file, and an hour of budget. `binwalk` found the
embedded archive, `foremost` carved it out, and the flag was in a config file
that had been "deleted" by removing the directory entry only.

```bash
binwalk -e evidence.img
foremost -i evidence.img -o carved/
rg -i 'flag\{' carved/
```

## Notes, not memory

Every challenge gets a folder and a `notes.md`. The template is three
headings — **what I see**, **what I tried**, **what is left**. When I rotate
to a different challenge and come back two hours later, the third heading is
the only thing I need to read.

| Directory | What goes in it |
| --- | --- |
| `scans/` | Raw tool output, never edited |
| `loot/` | Credentials, tokens, downloaded files |
| `notes.md` | The three headings above |

![A directory tree with one folder per challenge, each holding scans, loot and a notes file](../../assets/images/ctf-notes-layout.png)

## Lessons Learned

- Script the boring first pass. It runs while you read the challenge text.
- Build the target-specific wordlist during the event, not before it.
- Write down what you *ruled out*. It is worth as much as what you found.
- Stop guessing at minute fifteen and go read the source again.
