import { createHash } from 'node:crypto';
import { readdir, readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import type { AstroIntegration } from 'astro';

/**
 * Adds a Content-Security-Policy <meta> tag to every built page.
 *
 * GitHub Pages can't send headers, so the policy goes in the page itself. It
 * runs after the build because Astro inlines small scripts, and each one has to
 * be allowed by the SHA-256 hash of its exact contents; anything else, from
 * anywhere, is refused by the browser. Styles may be inline (code highlighting
 * uses style attributes), but only from this site. Dev mode is left alone.
 *
 * Adding a third-party script, font, image or embed will be blocked by this —
 * that's the point. See the Privacy page.
 */

const POLICY = (scriptHashes: string[]) =>
  [
    "default-src 'self'",
    `script-src 'self' ${scriptHashes.map((h) => `'sha256-${h}'`).join(' ')}`.trim(),
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data:",
    // data: covers the tiny wordmark font, which the build inlines into the CSS.
    "font-src 'self' data:",
    "connect-src 'none'",
    "object-src 'none'",
    "frame-src 'none'",
    "base-uri 'none'",
    "form-action 'none'",
    'upgrade-insecure-requests',
  ].join('; ');

const INLINE_SCRIPT = /<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/g;

async function* htmlFiles(dir: string): AsyncGenerator<string> {
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) yield* htmlFiles(path);
    else if (entry.name.endsWith('.html')) yield path;
  }
}

export default function csp(): AstroIntegration {
  return {
    name: 'csp-meta',
    hooks: {
      'astro:build:done': async ({ dir, logger }) => {
        let pages = 0;
        for await (const file of htmlFiles(fileURLToPath(dir))) {
          const html = await readFile(file, 'utf8');
          const hashes = [...html.matchAll(INLINE_SCRIPT)].map(([, body]) =>
            createHash('sha256').update(body, 'utf8').digest('base64'),
          );
          const meta = `<meta http-equiv="Content-Security-Policy" content="${POLICY([...new Set(hashes)])}">`;
          // Straight after <meta charset>, so it applies before anything loads.
          const out = html.replace(/(<meta charset="utf-8"\s*\/?>)/i, `$1${meta}`);
          if (out === html) throw new Error(`csp: no <meta charset> in ${file}`);
          await writeFile(file, out);
          pages += 1;
        }
        logger.info(`Content-Security-Policy added to ${pages} pages`);
      },
    },
  };
}
