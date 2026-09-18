import type { ShikiTransformer } from 'shiki';

/**
 * Terminal styling for shell code blocks (bash, sh, zsh, shell, console).
 *
 * - If any line starts with `$ `, the block is a session: those lines are
 *   commands (the `$ ` is removed from the source and drawn by CSS instead),
 *   and every other line is output, shown dimmed.
 * - Otherwise every line is a command, except blank lines and `#` comments.
 *
 * Lines following one that ends in `\` are continuations of that command and
 * get no prompt. The copy button copies commands only, never prompts or output.
 */

const SHELLS = new Set(['bash', 'sh', 'shell', 'zsh', 'console', 'shellsession']);

type Kind = 'cmd' | 'cont' | 'output' | 'plain';

function classify(code: string): { code: string; kinds: Kind[] } {
  const lines = code.split('\n');
  const session = lines.some((l) => /^\$( |$)/.test(l));
  const kinds: Kind[] = [];

  lines.forEach((line, i) => {
    const prev = kinds[i - 1];
    const continues =
      (prev === 'cmd' || prev === 'cont') && lines[i - 1].trimEnd().endsWith('\\');

    if (continues) {
      kinds.push('cont');
    } else if (session) {
      if (/^\$( |$)/.test(line)) {
        lines[i] = line.replace(/^\$ ?/, '');
        kinds.push('cmd');
      } else {
        kinds.push(line.trim() ? 'output' : 'plain');
      }
    } else {
      kinds.push(line.trim() && !line.trimStart().startsWith('#') ? 'cmd' : 'plain');
    }
  });

  return { code: lines.join('\n'), kinds };
}

export function terminalTransformer(): ShikiTransformer {
  let kinds: Kind[] = [];

  return {
    name: 'terminal',
    preprocess(code, options) {
      kinds = [];
      if (!SHELLS.has(options.lang)) return;
      const result = classify(code);
      if (!result.kinds.includes('cmd')) return;
      kinds = result.kinds;
      return result.code;
    },
    pre(node) {
      if (kinds.length) this.addClassToHast(node, 'is-terminal');
    },
    line(node, line) {
      const kind = kinds[line - 1];
      if (kind && kind !== 'plain') this.addClassToHast(node, `line--${kind}`);
    },
  };
}
