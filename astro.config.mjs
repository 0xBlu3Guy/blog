// @ts-check
import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';
import { rehypeHeadingIds } from '@astrojs/markdown-remark';
import csp from './src/integrations/csp.ts';
import rehypeHeadingLinks from './src/lib/rehype-heading-links.ts';
import remarkCallouts from './src/lib/remark-callouts.ts';
import { terminalTransformer } from './src/lib/shiki-terminal.ts';

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
  integrations: [sitemap(), csp()],
  markdown: {
    // `> [!NOTE]`, `> [!TIP]`, `> [!IMPORTANT]`, `> [!WARNING]`, `> [!CAUTION]`,
    // and `> [!SPOILER]` for collapsed blocks.
    remarkPlugins: [remarkCallouts],
    // IDs first, so every heading has one to link to.
    rehypePlugins: [rehypeHeadingIds, rehypeHeadingLinks],
    shikiConfig: {
      theme: 'github-dark-dimmed',
      // Prompts and dimmed output for shell blocks.
      transformers: [terminalTransformer()],
      wrap: false,
    },
  },
});
