# Sobhan's Blog

A small, fast, Markdown-driven blog built with [Astro](https://astro.build) and
deployed to GitHub Pages. No database, no backend, no admin panel — a post is a
`.md` file you commit.

```
Markdown file  →  git push  →  GitHub Actions  →  published
```

---

## Publishing a new article

**1. Create a Markdown file** in `src/content/posts/`. The filename becomes the
URL, so keep it lowercase and hyphenated:

```bash
$EDITOR src/content/posts/my-new-writeup.md
```

`my-new-writeup.md` is published at `/posts/my-new-writeup`.

**2. Add frontmatter** at the top of the file:

```yaml
---
title: "My New Writeup"
description: "What I learned..."
date: 2026-09-20
tags:
  - CTF
  - Linux
  - Security
---
```

**3. Write the article** in Markdown below the frontmatter.

**4. Preview it locally:**

```bash
npm run dev          # http://localhost:4321
```

**5. Commit and push:**

```bash
git add .
git commit -m "Add my new writeup"
git push
```

**6. GitHub Actions builds and deploys the site.** Watch it in the *Actions*
tab; it usually takes under a minute.

That's the whole workflow. The homepage, the tag pages, the post count on each
tag, the RSS feed and the sitemap all update themselves — there is no index
file to edit.

---

## Local development

```bash
npm install          # once
npm run dev          # dev server with live reload at http://localhost:4321
npm run build        # type-check + production build into dist/
npm run preview      # serve dist/ exactly as it will be deployed
```

`npm run build` runs `astro check` first, so a broken link to a component or a
type error fails the build before it can ship.

---

## Frontmatter reference

| Field | Required | Type | Notes |
| --- | --- | --- | --- |
| `title` | yes | string | Used as the page `<h1>` and `<title>` |
| `date` | yes | date | `YYYY-MM-DD`. Sorting is newest first |
| `description` | no | string | Used on cards and in meta tags. Falls back to the first paragraph |
| `tags` | no | string[] | Any number of tags. Defaults to none |
| `draft` | no | boolean | `true` keeps the post out of the deployed site |
| `image` | no | path | Social preview + header image, relative to the post file |
| `imageAlt` | no | string | Alt text for `image` |
| `author` | no | string | Defaults to the site author |

Frontmatter is validated during the build (`src/content.config.ts`). A missing
`title` or a `date` that isn't a date fails the build with a message naming the
file and the field — it never ships a half-broken post.

### Tags

Add them to the frontmatter and that's it:

```yaml
tags:
  - CTF
  - Web Security
```

Each tag automatically gets a page at `/tags/<slug>` — `Web Security` becomes
`/tags/web-security`. A post with three tags appears under all three. Post
counts on `/tags` are computed from the posts themselves.

Tags are matched case-insensitively, so `CTF` and `ctf` end up on the same
page.

To add a one-line description to a tag page, add the slug to `tagDescriptions`
in `src/site.config.ts`. This is optional — tag pages exist with or without it.

### Draft posts

```yaml
---
title: "My New Writeup"
date: 2026-09-20
draft: true
tags:
  - CTF
---
```

Drafts are visible in `npm run dev` so you can preview them, and are excluded
from `npm run build` — so they never reach GitHub Pages. See
`src/content/posts/example-draft-post.md`.

### Images

Put images in `src/assets/images/` and reference them relative to the post:

```markdown
![Burp Suite request](../../assets/images/burp-request.png)
```

Images referenced this way are optimised at build time (resized, converted to
WebP, given width/height attributes) and get a hashed filename, so they work
correctly under the GitHub Pages subpath. Always write real alt text.

A frontmatter `image:` is used as the article's header image and as the
Open Graph / Twitter preview image.

Files in `public/` are copied verbatim instead and are referenced from the site
root (`/favicon.svg`) — use it for things that must keep their exact filename.

### Code blocks

Fence the block and name the language:

````markdown
```bash
nmap -sV target.example.com
```
````

Syntax highlighting is done at build time (Shiki) with a theme for each colour
mode, so there is no highlighting JavaScript in the page. Every block gets a
copy button on hover and scrolls horizontally on small screens. Inline code
uses single backticks: `` `--min-rate` ``.

---

## Project structure

```text
blog/
├── src/
│   ├── assets/images/        # images referenced from posts (optimised)
│   ├── components/           # Header, Footer, PostCard, Tag, Search, …
│   ├── content/posts/        # ← your posts live here
│   ├── layouts/              # BaseLayout, PostLayout
│   ├── lib/                  # post/tag queries, slug + reading-time helpers
│   ├── pages/
│   │   ├── index.astro       # homepage
│   │   ├── about.astro
│   │   ├── 404.astro
│   │   ├── rss.xml.ts        # RSS feed
│   │   ├── posts/[...slug].astro
│   │   └── tags/[tag].astro  # one page per tag, generated
│   ├── styles/global.css     # all styling, plain CSS with design tokens
│   ├── content.config.ts     # frontmatter schema
│   └── site.config.ts        # ← your name, links, intro text
├── public/                   # copied as-is (favicon, robots.txt)
├── .github/workflows/deploy.yml
└── astro.config.mjs
```

Personal details (title, author, intro paragraph, GitHub and LinkedIn links)
all live in **`src/site.config.ts`**. Editing components isn't necessary for
normal changes.

---

## First-time GitHub Pages setup

1. Create a repository named **`blog`** and push this project to `main`.

   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin git@github.com:0xBlu3Guy/blog.git
   git push -u origin main
   ```

2. In the repository, open **Settings → Pages** and set **Source** to
   **GitHub Actions**.

3. Push to `main`. The workflow in `.github/workflows/deploy.yml` installs
   dependencies, builds, and publishes `dist/`.

The site will be at `https://0xblu3guy.github.io/blog`.

`astro.config.mjs` derives the site URL and base path from the repository name
at build time, so nothing needs editing if you name the repo something else —
and if you rename it to `0xBlu3Guy.github.io`, it will correctly serve from the
domain root instead.

---

## What's included

- Markdown posts with validated frontmatter
- Automatic tag pages, tag index and post counts
- Reading time and automatic excerpts
- Dark mode (default) and light mode, remembered in `localStorage`
- Client-side search over title, description and tags on the homepage
- Syntax-highlighted code blocks with copy buttons
- RSS feed, sitemap, Open Graph and Twitter card metadata
- Responsive layout, semantic HTML, keyboard-navigable, reduced-motion support

## Customising

| Change | Where |
| --- | --- |
| Name, intro text, social links | `src/site.config.ts` |
| Tag page descriptions | `tagDescriptions` in `src/site.config.ts` |
| Colours, spacing, fonts | the token block at the top of `src/styles/global.css` |
| About page copy | `src/pages/about.astro` |
| Navigation items | `links` array in `src/components/Header.astro` |
| Code highlighting themes | `shikiConfig` in `astro.config.mjs` |
