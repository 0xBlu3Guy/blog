---
title: "Example Draft Post"
description: "This post is a draft — it shows up in local development and is excluded from the deployed site."
date: 2026-09-01
draft: true
tags:
  - CTF
---

This file exists to show how drafts behave.

Because its frontmatter contains `draft: true`, it appears while you run
`npm run dev` so you can preview it, and it is left out of `npm run build` —
so it never reaches GitHub Pages.

Remove the `draft: true` line (or set it to `false`) when the post is ready,
then commit and push.

## Adding an image

Drop the file in `src/assets/images/`, then reference it relative to this post:

![A directory tree with one folder per challenge](../../assets/images/ctf-notes-layout.png)

That is the whole workflow — no config, no import, no manifest.

## Callouts

Start a blockquote with a marker to turn it into a callout:

> [!NOTE]
> Plain context the reader should keep in mind.

> [!TIP] Faster recon
> Text after the marker replaces the default title.

> [!IMPORTANT]
> Something the reader must not skip.

> [!WARNING]
> Don't run this against a host you're not authorised to test.

> [!CAUTION]
> This one breaks things.

## Terminal blocks

Shell blocks (`bash`, `sh`, `zsh`, `shell`, `console`) get a `$` prompt on
every command. The prompt isn't part of the text, so the Copy button and
manual selection both skip it:

```bash
nmap -sV -p- --min-rate 2000 target.example.com
ffuf -u http://target.example.com/FUZZ \
     -w ~/wordlists/common.txt
```

Start lines with `$ ` to show a session. Those lines are commands and the rest
is output, shown dimmed. Copy takes the commands only:

```bash
$ whoami
www-data
$ sudo -l
User www-data may run the following commands on target:
    (root) NOPASSWD: /usr/bin/find
$ sudo find . -exec /bin/sh \; -quit
```

## Footnotes

Footnotes use standard Markdown.[^1] They're collected at the end of the post,
and each one links back to where it was cited.[^scope]

[^1]: Like this one.
[^scope]: Named footnotes work too, and are numbered automatically.

