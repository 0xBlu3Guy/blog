---
title: "Example Draft Post"
description: "This post is a draft — it shows up in local development and is excluded from the deployed site."
date: 2026-09-20
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
