/**
 * Appends a "#" link to every h2–h4 in a post, so readers can copy a link to
 * one section. Needs heading IDs, so it runs after rehypeHeadingIds.
 */

interface Node {
  type: string;
  tagName?: string;
  properties?: Record<string, unknown>;
  children?: Node[];
  value?: string;
}

const HEADINGS = new Set(['h2', 'h3', 'h4']);

// The footnotes section's label is a heading too, but not a section of the post.
const SKIP_IDS = new Set(['footnote-label']);

function walk(node: Node): void {
  for (const child of node.children ?? []) walk(child);

  const id = node.properties?.id;
  if (node.type !== 'element' || !HEADINGS.has(node.tagName!) || typeof id !== 'string') return;
  if (SKIP_IDS.has(id)) return;

  node.children!.push({
    type: 'element',
    tagName: 'a',
    properties: {
      className: ['heading-anchor'],
      href: `#${id}`,
      ariaLabel: 'Link to this section',
    },
    children: [{ type: 'text', value: '#' }],
  });
}

export default function rehypeHeadingLinks() {
  return (tree: Node) => walk(tree);
}
