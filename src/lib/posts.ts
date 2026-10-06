import { getCollection, type CollectionEntry } from 'astro:content';
import { slugify } from './utils';

export type Post = CollectionEntry<'posts'>;

/**
 * Every publishable post, newest first.
 *
 * Drafts are shown while running `astro dev` so you can preview work in
 * progress, and dropped from any production build.
 */
export async function getPosts(): Promise<Post[]> {
  const posts = await getCollection('posts', ({ data }) =>
    import.meta.env.DEV ? true : data.draft !== true,
  );
  return posts.sort((a, b) => b.data.date.getTime() - a.data.date.getTime());
}

/**
 * Posts most related to `post`, ranked by how many tags they share with it.
 *
 * Tags are compared by slug, so "Bug Bounty" and "bug bounty" count as a match.
 * The post itself is never returned, posts sharing no tag are dropped, and ties
 * are broken by date (newest first). Drafts follow the same dev/prod rule as
 * everywhere else because the candidates come from `getPosts`.
 */
export async function getRelatedPosts(post: Post, limit = 3): Promise<Post[]> {
  const tagSlugs = new Set(post.data.tags.map(slugify).filter(Boolean));
  if (tagSlugs.size === 0) return [];

  const posts = await getPosts();
  return posts
    .filter((candidate) => candidate.id !== post.id)
    .map((candidate) => ({
      candidate,
      shared: candidate.data.tags.filter((tag) => tagSlugs.has(slugify(tag)))
        .length,
    }))
    .filter(({ shared }) => shared > 0)
    .sort(
      (a, b) =>
        b.shared - a.shared ||
        b.candidate.data.date.getTime() - a.candidate.data.date.getTime(),
    )
    .slice(0, limit)
    .map(({ candidate }) => candidate);
}

export interface TagSummary {
  /** The tag as written in frontmatter, e.g. "Web Security". */
  name: string;
  /** The URL segment, e.g. "web-security". */
  slug: string;
  posts: Post[];
}

/**
 * Collect every tag used across all posts, with its posts attached.
 *
 * Tags are matched case-insensitively by slug, so "Bug Bounty" and "bug bounty"
 * end up on the same page. The display name is taken from the first post that
 * uses the tag (which, because posts are sorted, is the most recent one).
 */
export async function getTags(): Promise<TagSummary[]> {
  const posts = await getPosts();
  const tags = new Map<string, TagSummary>();

  for (const post of posts) {
    for (const name of post.data.tags) {
      const slug = slugify(name);
      if (!slug) continue;
      const existing = tags.get(slug);
      if (existing) {
        existing.posts.push(post);
      } else {
        tags.set(slug, { name, slug, posts: [post] });
      }
    }
  }

  return [...tags.values()].sort(
    (a, b) => b.posts.length - a.posts.length || a.name.localeCompare(b.name),
  );
}
