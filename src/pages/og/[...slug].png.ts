import type { APIRoute, GetStaticPaths } from 'astro';
import { getPosts, type Post } from '../../lib/posts';
import { renderOgImage } from '../../lib/og-image';

// One preview card per post, at /og/<post-slug>.png. Posts with their own
// frontmatter `image` still get one, but that image is what the page links.
export const getStaticPaths = (async () => {
  const posts = await getPosts();
  return posts.map((post) => ({ params: { slug: post.id }, props: { post } }));
}) satisfies GetStaticPaths;

export const GET: APIRoute<{ post: Post }> = async ({ props }) => {
  const { title, tags, date } = props.post.data;
  const png = await renderOgImage({ title, tags, date });
  return new Response(new Uint8Array(png), { headers: { 'Content-Type': 'image/png' } });
};
