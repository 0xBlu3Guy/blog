import rss from '@astrojs/rss';
import type { APIContext } from 'astro';
import { getPosts } from '../lib/posts';
import { site } from '../site.config';
import { excerpt, href } from '../lib/utils';

export async function GET(context: APIContext) {
  const posts = await getPosts();

  return rss({
    title: site.title,
    description: site.description,
    // The channel link is the blog root, which includes the base path.
    site: new URL(import.meta.env.BASE_URL, context.site!),
    trailingSlash: false,
    items: posts.map((post) => ({
      title: post.data.title,
      description: post.data.description || excerpt(post.body ?? ''),
      pubDate: post.data.date,
      categories: [...post.data.tags],
      link: href(`/posts/${post.id}`),
    })),
    customData: `<language>${site.lang}</language>`,
  });
}
