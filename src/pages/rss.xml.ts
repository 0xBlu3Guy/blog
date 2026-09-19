import rss from '@astrojs/rss';
import type { APIContext } from 'astro';
import { experimental_AstroContainer as AstroContainer } from 'astro/container';
import { render } from 'astro:content';
import { getPosts } from '../lib/posts';
import { site } from '../site.config';
import { excerpt, href } from '../lib/utils';

/**
 * Feed readers get the whole post, not just the description. Posts are
 * rendered with the container API (rather than `post.rendered.html`) so
 * optimised images come out as real URLs.
 */

// Feed readers show the HTML out of context, so every site-relative URL has to
// become absolute, and page-only UI (the "#" heading links) is dropped.
function forFeed(html: string, origin: string): string {
  return html
    .replace(/<a class="heading-anchor"[^>]*>#<\/a>/g, '')
    .replace(/\b(src|href)="\/(?!\/)/g, `$1="${origin}/`)
    .replace(/\bsrcset="([^"]*)"/g, (_, set: string) =>
      `srcset="${set.replace(/(^|,\s*)\/(?!\/)/g, `$1${origin}/`)}"`,
    );
}

export async function GET(context: APIContext) {
  const posts = await getPosts();
  const container = await AstroContainer.create();
  const origin = context.site!.origin;

  const items = await Promise.all(
    posts.map(async (post) => {
      const { Content } = await render(post);
      const html = await container.renderToString(Content);
      return {
        title: post.data.title,
        description: post.data.description || excerpt(post.body ?? ''),
        pubDate: post.data.date,
        categories: [...post.data.tags],
        link: href(`/posts/${post.id}`),
        content: forFeed(html, origin),
      };
    }),
  );

  return rss({
    title: site.title,
    description: site.description,
    // The channel link is the blog root, which includes the base path.
    site: new URL(import.meta.env.BASE_URL, context.site!),
    trailingSlash: false,
    items,
    customData: `<language>${site.lang}</language>`,
  });
}
