// @ts-check
import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';
import remarkCallouts from './src/lib/remark-callouts.ts';

/**
 * On GitHub Actions we can derive the deployed URL from the environment, so the
 * same config works for a user site (0xBlu3Guy.github.io) and a project site
 * (0xBlu3Guy.github.io/blog) without editing anything.
 *
 * Locally (or anywhere else) it falls back to the values in src/site.config.ts.
 */
const repository = process.env.GITHUB_REPOSITORY; // "owner/repo"
const owner = process.env.GITHUB_REPOSITORY_OWNER;

let site = 'https://0xblu3guy.github.io';
let base = '/blog';

if (repository && owner) {
  const repo = repository.split('/')[1];
  const isUserSite = repo.toLowerCase() === `${owner.toLowerCase()}.github.io`;
  site = `https://${owner.toLowerCase()}.github.io`;
  base = isUserSite ? '/' : `/${repo}`;
}

export default defineConfig({
  site,
  base,
  trailingSlash: 'ignore',
  integrations: [sitemap()],
  markdown: {
    // `> [!NOTE]`, `> [!TIP]`, `> [!IMPORTANT]`, `> [!WARNING]`, `> [!CAUTION]`
    remarkPlugins: [remarkCallouts],
    shikiConfig: {
      // Two themes so code blocks follow the site's dark/light mode.
      themes: { light: 'github-light', dark: 'github-dark-dimmed' },
      // Emit CSS variables only, so global.css can pick the theme that matches
      // the current colour mode instead of baking one in.
      defaultColor: false,
      wrap: false,
    },
  },
});
