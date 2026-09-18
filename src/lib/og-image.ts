import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import satori from 'satori';
import sharp from 'sharp';
import { formatDate } from './utils';

/**
 * Renders a 1200×630 social preview card for a post at build time.
 *
 * Satori lays out the element tree below (it understands a flexbox subset of
 * CSS) into an SVG, and sharp rasterises that to PNG. Satori can't read
 * woff2, so the fonts come from the @fontsource packages' woff files.
 */

const WIDTH = 1200;
const HEIGHT = 630;

// The site's dark palette (see :root in global.css).
const BG = '#0b0e14';
const BORDER = '#222a39';
const TEXT = '#c6cfdc';
const HEADING = '#e6ebf3';
const MUTED = '#8e9aae';
const ACCENT = '#5b9dff';
const ACCENT_BORDER = 'rgba(91, 157, 255, 0.45)';

const fontFile = (pkg: string, file: string) =>
  readFile(resolve(process.cwd(), 'node_modules/@fontsource', pkg, 'files', file));

let fonts: Promise<Parameters<typeof satori>[1]['fonts']> | undefined;

function loadFonts() {
  fonts ??= Promise.all([
    fontFile('inter-tight', 'inter-tight-latin-500-normal.woff'),
    fontFile('inter-tight', 'inter-tight-latin-700-normal.woff'),
    fontFile('chakra-petch', 'chakra-petch-latin-700-normal.woff'),
  ]).then(([regular, bold, wordmark]) => [
    { name: 'Inter Tight', data: regular, weight: 500, style: 'normal' },
    { name: 'Inter Tight', data: bold, weight: 700, style: 'normal' },
    { name: 'Chakra Petch', data: wordmark, weight: 700, style: 'normal' },
  ]);
  return fonts;
}

type El = { type: string; props: Record<string, unknown> };

const el = (type: string, style: Record<string, unknown>, children?: unknown): El => ({
  type,
  props: { style, children },
});

/** Shrinks long titles so they still fit in three lines. */
function titleSize(title: string): number {
  if (title.length <= 36) return 76;
  if (title.length <= 60) return 64;
  return 52;
}

export async function renderOgImage(post: {
  title: string;
  tags: string[];
  date: Date;
}): Promise<Buffer> {
  const wordmark = el('div', { display: 'flex', fontFamily: 'Chakra Petch', fontSize: 38, color: TEXT }, [
    el('span', {}, '0x'),
    el('span', { color: ACCENT }, 'Blu3'),
    el('span', {}, 'Guy'),
  ]);

  const title = el(
    'div',
    {
      display: 'flex',
      fontSize: titleSize(post.title),
      fontWeight: 700,
      lineHeight: 1.12,
      letterSpacing: '-0.02em',
      color: HEADING,
      maxWidth: 1000,
    },
    post.title,
  );

  const tags = el(
    'div',
    { display: 'flex', flexWrap: 'wrap', gap: 12 },
    post.tags.slice(0, 4).map((tag) =>
      el(
        'div',
        {
          display: 'flex',
          padding: '6px 18px',
          fontSize: 24,
          color: MUTED,
          border: `2px solid ${ACCENT_BORDER}`,
          borderRadius: 999,
        },
        tag,
      ),
    ),
  );

  const footer = el(
    'div',
    { display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 24 },
    [tags, el('div', { display: 'flex', fontSize: 26, color: MUTED }, formatDate(post.date))],
  );

  const card = el(
    'div',
    {
      display: 'flex',
      flexDirection: 'column',
      justifyContent: 'space-between',
      width: '100%',
      height: '100%',
      padding: '64px 72px',
      fontFamily: 'Inter Tight',
      fontWeight: 500,
      background: BG,
      borderTop: `8px solid ${ACCENT}`,
      boxShadow: `inset 0 0 0 2px ${BORDER}`,
    },
    [wordmark, title, footer],
  );

  const svg = await satori(card as Parameters<typeof satori>[0], {
    width: WIDTH,
    height: HEIGHT,
    fonts: await loadFonts(),
  });
  return sharp(Buffer.from(svg)).png().toBuffer();
}
