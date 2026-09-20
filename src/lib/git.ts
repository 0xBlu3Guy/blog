import { execFileSync } from 'node:child_process';

/**
 * Last commit date per post file, so a revised post can say "Updated …"
 * without maintaining a field by hand. A post's own `updated:` frontmatter
 * wins over this.
 *
 * One `git log` call covers every post: commits come newest first, so the
 * first time a file appears is its last change. A file with a single commit
 * has never been revised — it was just added — so it gets no date at all.
 * Outside a git checkout (or in a shallow clone with no history) the map is
 * simply empty and nothing is shown.
 */

const POSTS_DIR = 'src/content/posts';

interface FileHistory {
  last: Date;
  commits: number;
}

let dates: Map<string, FileHistory> | undefined;

function readGitDates(): Map<string, FileHistory> {
  const map = new Map<string, FileHistory>();
  let log: string;
  try {
    log = execFileSync(
      'git',
      ['log', '--pretty=format:%cI', '--name-only', '--no-merges', '--', POSTS_DIR],
      { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] },
    );
  } catch {
    return map; // not a git checkout, or git isn't installed
  }

  let commitDate: Date | undefined;
  for (const line of log.split('\n')) {
    if (!line.trim()) continue;
    if (/^\d{4}-\d{2}-\d{2}T/.test(line)) {
      commitDate = new Date(line);
    } else if (commitDate && line.startsWith(`${POSTS_DIR}/`)) {
      // The post's id is its filename without the extension.
      const id = line.slice(POSTS_DIR.length + 1).replace(/\.mdx?$/, '');
      const seen = map.get(id);
      if (seen) seen.commits += 1;
      else map.set(id, { last: commitDate, commits: 1 });
    }
  }
  return map;
}

/** When a post's file was last changed, if it has been changed since it was added. */
export function lastCommitDate(postId: string): Date | undefined {
  dates ??= readGitDates();
  const history = dates.get(postId);
  return history && history.commits > 1 ? history.last : undefined;
}

/**
 * The date to show as "Updated", or undefined when there's nothing worth
 * showing: a post edited on the day it was published isn't "updated".
 */
export function updatedDate(
  postId: string,
  published: Date,
  fromFrontmatter?: Date,
): Date | undefined {
  const candidate = fromFrontmatter ?? lastCommitDate(postId);
  if (!candidate) return undefined;
  const dayLater = new Date(published).setHours(24, 0, 0, 0);
  return candidate.getTime() > dayLater ? candidate : undefined;
}
