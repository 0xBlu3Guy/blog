import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import satori from 'satori';
import sharp from 'sharp';
import { formatDate } from './utils';

/**
 * Renders 1200×630 social preview cards at build time — one per post, one per
 * tag page — in the same style as the site banner (public/og-default.jpg): the
 * emblem and wordmark, the page's own heading, and a row of "signal" bars along
 * the bottom whose pattern is seeded from that heading, so every card differs
 * and the same page always renders the same one.
 *
 * Satori lays out the element tree below (it understands a flexbox subset of
 * CSS) into an SVG, and sharp rasterises that to PNG. Satori can't read
 * woff2, so the fonts come from the @fontsource packages' woff files.
 */

const WIDTH = 1200;
const HEIGHT = 630;

// Banner palette.
const BG = '#070a10';
const HEADING = '#e6ebf3';
const TEXT = '#c6cfdc';
const MUTED = '#8e9aae';
const BLUE = '#2f8bff';
const TAG_BORDER = 'rgba(91, 157, 255, 0.45)';

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

// The emblem with its dark background turned into transparency (Satori has no
// blend modes). 480×418.
let emblem: Promise<string> | undefined;

function loadEmblem() {
  emblem ??= readFile(resolve(process.cwd(), 'src/assets/brand/emblem.png')).then(
    (png) => `data:image/png;base64,${png.toString('base64')}`,
  );
  return emblem;
}

type El = { type: string; props: Record<string, unknown> };

const el = (type: string, style: Record<string, unknown>, children?: unknown): El => ({
  type,
  props: { style, children },
});

/** Shrinks long titles so they still fit in three lines. */
function titleSize(title: string): number {
  if (title.length <= 36) return 78;
  if (title.length <= 60) return 66;
  return 54;
}

/** A small seeded PRNG (mulberry32), so a title always yields the same bars. */
function seeded(text: string): () => number {
  let h = 2166136261;
  for (const c of text) h = Math.imul(h ^ c.charCodeAt(0), 16777619);
  return () => {
    h = (h + 0x6d2b79f5) | 0;
    let t = Math.imul(h ^ (h >>> 15), 1 | h);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function signalBars(title: string): El {
  const random = seeded(title);
  const step = 13.5;
  const count = Math.floor((WIDTH - 22) / step) + 1;
  const offset = (WIDTH - (count - 1) * step - 3) / 2; // centre the row
  const bars = Array.from({ length: count }, (_, i) => {
    const height = Math.round(10 + random() ** 2 * 100);
    const alpha = (0.25 + random() * 0.5).toFixed(2);
    const rgb = random() < 0.25 ? '41, 182, 255' : '47, 139, 255'; // cyan or blue
    return el('div', {
      position: 'absolute',
      left: offset + i * step,
      bottom: 0,
      width: 3,
      height,
      borderRadius: '2px 2px 0 0',
      backgroundImage: `linear-gradient(to top, rgba(${rgb}, ${alpha}), rgba(${rgb}, 0))`,
    });
  });
  return el(
    'div',
    { position: 'absolute', left: 0, bottom: 0, width: WIDTH, height: 110, display: 'flex' },
    bars,
  );
}

async function brandRow(): Promise<El> {
  return el('div', { display: 'flex', alignItems: 'center', gap: 18 }, [
    { type: 'img', props: { src: await loadEmblem(), width: 92, height: 80, style: {} } },
    el('div', { display: 'flex', fontFamily: 'Chakra Petch', fontSize: 36, color: HEADING }, [
      el('span', {}, '0x'),
      el('span', { color: BLUE }, 'Blu3'),
      el('span', {}, 'Guy'),
    ]),
  ]);
}

/** The shared frame: background, glow, bars, and the three stacked rows. */
async function card(seed: string, heading: El, footer: El): Promise<Buffer> {
  const content = el(
    'div',
    {
      display: 'flex',
      flexDirection: 'column',
      justifyContent: 'space-between',
      width: '100%',
      height: 520,
      padding: '52px 72px 34px',
    },
    [await brandRow(), heading, footer],
  );

  const frame = el(
    'div',
    {
      position: 'relative',
      display: 'flex',
      width: '100%',
      height: '100%',
      fontFamily: 'Inter Tight',
      fontWeight: 500,
      backgroundColor: BG,
      backgroundImage:
        'radial-gradient(ellipse 60% 45% at 50% 100%, rgba(47, 139, 255, 0.14), rgba(47, 139, 255, 0))',
    },
    [content, signalBars(seed)],
  );

  const svg = await satori(frame as Parameters<typeof satori>[0], {
    width: WIDTH,
    height: HEIGHT,
    fonts: await loadFonts(),
  });
  return sharp(Buffer.from(svg)).png().toBuffer();
}

function tagPills(tags: string[]): El {
  return el(
    'div',
    { display: 'flex', flexWrap: 'wrap', gap: 12 },
    tags.slice(0, 4).map((tag) =>
      el(
        'div',
        {
          display: 'flex',
          padding: '6px 18px',
          fontSize: 23,
          color: TEXT,
          border: `2px solid ${TAG_BORDER}`,
          borderRadius: 999,
        },
        tag,
      ),
    ),
  );
}

const heading = (text: string, size: number) =>
  el(
    'div',
    {
      display: 'flex',
      fontSize: size,
      fontWeight: 700,
      lineHeight: 1.1,
      letterSpacing: '-0.02em',
      color: HEADING,
      maxWidth: 1040,
    },
    text,
  );

/** A post's card: title, tags and date. */
export async function renderOgImage(post: {
  title: string;
  tags: string[];
  date: Date;
}): Promise<Buffer> {
  const footer = el(
    'div',
    { display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 24 },
    [
      tagPills(post.tags),
      el('div', { display: 'flex', fontSize: 25, color: MUTED }, formatDate(post.date)),
    ],
  );
  return card(post.title, heading(post.title, titleSize(post.title)), footer);
}

/** A tag page's card: the tag name and how many posts use it. */
export async function renderTagImage(tag: {
  name: string;
  count: number;
  blurb?: string;
}): Promise<Buffer> {
  const label = el(
    'div',
    { display: 'flex', alignItems: 'baseline', gap: 10, maxWidth: 1040 },
    [
      el('span', { display: 'flex', fontSize: 74, fontWeight: 700, color: BLUE }, '#'),
      heading(tag.name, titleSize(tag.name)),
    ],
  );
  const posts = `${tag.count} ${tag.count === 1 ? 'post' : 'posts'}`;
  const footer = el(
    'div',
    { display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 24 },
    [
      el(
        'div',
        { display: 'flex', fontSize: 25, color: MUTED, maxWidth: 820 },
        tag.blurb ?? '',
      ),
      el('div', { display: 'flex', fontSize: 25, color: TEXT }, posts),
    ],
  );
  return card(tag.name, label, footer);
}
