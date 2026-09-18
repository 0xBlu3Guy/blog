/**
 * Turns GitHub-style alert blockquotes into callout boxes:
 *
 *   > [!WARNING]
 *   > Don't run this against a host you don't own.
 *
 * An optional title can follow the marker on the same line
 * (`> [!TIP] Faster recon`); otherwise the type name is used. Unknown types
 * are left as ordinary blockquotes.
 */

const TYPES: Record<string, string> = {
  note: 'Note',
  tip: 'Tip',
  important: 'Important',
  warning: 'Warning',
  caution: 'Caution',
};

const MARKER = /^\[!(\w+)\][ \t]*([^\n]*)(?:\n|$)/;

interface Node {
  type: string;
  value?: string;
  children?: Node[];
  data?: Record<string, unknown>;
}

function transform(node: Node): void {
  for (const child of node.children ?? []) transform(child);
  if (node.type !== 'blockquote') return;

  const first = node.children?.[0];
  const text = first?.type === 'paragraph' ? first.children?.[0] : undefined;
  if (!first || text?.type !== 'text' || !text.value) return;

  const match = MARKER.exec(text.value);
  const type = match?.[1].toLowerCase();
  if (!match || !type || !(type in TYPES)) return;

  text.value = text.value.slice(match[0].length);
  // Drop the paragraph (or its leading line break) if the marker was all it held.
  if (!text.value) first.children!.shift();
  if (first.children![0]?.type === 'break') first.children!.shift();
  if (first.children!.length === 0) node.children!.shift();

  node.data = {
    hName: 'div',
    hProperties: { className: ['callout', `callout--${type}`], role: 'note' },
  };
  node.children!.unshift({
    type: 'paragraph',
    data: { hProperties: { className: ['callout__title'] } },
    children: [{ type: 'text', value: match[2].trim() || TYPES[type] }],
  });
}

export default function remarkCallouts() {
  return (tree: Node) => transform(tree);
}
