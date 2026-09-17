/** Words a typical reader gets through in a minute. */
const WORDS_PER_MINUTE = 200;

/**
 * Turn a tag like "Web Security" into a URL-safe slug like "web-security".
 * Used for both /tags/<slug> routes and post URLs.
 */
export function slugify(value: string): string {
  return value
    .normalize('NFKD')
    .replace(/[̀-ͯ]/g, '') // strip accents
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

/**
 * Estimate reading time from the raw Markdown body.
 *
 * We deliberately work on the raw body rather than rendered HTML so the
 * homepage and tag pages never have to render a post just to show "8 min read".
 */
export function readingTime(body: string): number {
  const text = body
    .replace(/```[\s\S]*?```/g, ' ') // fenced code blocks
    .replace(/`[^`]*`/g, ' ') // inline code
    .replace(/!\[[^\]]*\]\([^)]*\)/g, ' ') // images
    .replace(/\[([^\]]*)\]\([^)]*\)/g, '$1') // links -> link text
    .replace(/[#>*_~|-]/g, ' ');
  const words = text.split(/\s+/).filter(Boolean).length;
  return Math.max(1, Math.round(words / WORDS_PER_MINUTE));
}

/**
 * First paragraph of the body, used when a post has no `description`.
 */
export function excerpt(body: string, maxLength = 180): string {
  const firstParagraph = body
    .replace(/^---[\s\S]*?---/, '') // any stray frontmatter
    .replace(/```[\s\S]*?```/g, '')
    .split(/\n\s*\n/)
    .map((block) => block.trim())
    .find((block) => block && !block.startsWith('#') && !block.startsWith('!'));

  if (!firstParagraph) return '';

  const plain = firstParagraph
    .replace(/!\[[^\]]*\]\([^)]*\)/g, '')
    .replace(/\[([^\]]*)\]\([^)]*\)/g, '$1')
    .replace(/[*_`>]/g, '')
    .replace(/\s+/g, ' ')
    .trim();

  return plain.length > maxLength
    ? `${plain.slice(0, maxLength).replace(/\s+\S*$/, '')}…`
    : plain;
}

/** "Sep 15, 2026" */
export function formatDate(date: Date): string {
  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    timeZone: 'UTC',
  });
}

/** "2026-09-15", for <time datetime="..."> */
export function isoDate(date: Date): string {
  return date.toISOString().slice(0, 10);
}

/**
 * Prefix an absolute in-site path with the configured base path so links keep
 * working when the site is served from a subdirectory (GitHub project pages).
 */
export function href(path: string): string {
  const base = import.meta.env.BASE_URL.replace(/\/+$/, '');
  return `${base}${path}` || '/';
}
