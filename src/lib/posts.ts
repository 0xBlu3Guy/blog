import { getCollection, type CollectionEntry } from 'astro:content';
import { slugify } from './utils';
import { tagList } from '../site.config';

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

export interface TagSummary {
  /** The tag as written in frontmatter, e.g. "Web Security". */
  name: string;
  /** The URL segment, e.g. "web-security". */
  slug: string;
  posts: Post[];
}

/**
 * Every tag: all the ones listed in site.config.ts (even with no posts yet),
 * plus any other tag a post uses, each with its posts attached. Sorted
 * alphabetically.
 *
 * Tags are matched case-insensitively by slug, so "Bug Bounty" and "bug bounty"
 * end up on the same page. Configured tags keep their configured name; others
 * take the name from the most recent post that uses them. `devOnly` tags are
 * left out of production builds.
 */
export async function getTags(): Promise<TagSummary[]> {
  const posts = await getPosts();
  const tags = new Map<string, TagSummary>();

  for (const { name, devOnly } of tagList) {
    if (devOnly && !import.meta.env.DEV) continue;
    tags.set(slugify(name), { name, slug: slugify(name), posts: [] });
  }

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

  return [...tags.values()].sort((a, b) =>
    a.name.localeCompare(b.name, undefined, { sensitivity: 'base' }),
  );
}
