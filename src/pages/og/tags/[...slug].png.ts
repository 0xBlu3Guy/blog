import type { APIRoute, GetStaticPaths } from 'astro';
import { getTags } from '../../../lib/posts';
import { renderTagImage } from '../../../lib/og-image';
import { tagDescriptions } from '../../../site.config';

// One preview card per tag page, at /og/tags/<slug>.png.
export const getStaticPaths = (async () => {
  const tags = await getTags();
  return tags.map((tag) => ({
    params: { slug: tag.slug },
    props: { name: tag.name, slug: tag.slug, count: tag.posts.length },
  }));
}) satisfies GetStaticPaths;

export const GET: APIRoute<{ name: string; slug: string; count: number }> = async ({ props }) => {
  const png = await renderTagImage({
    name: props.name,
    count: props.count,
    blurb: tagDescriptions[props.slug],
  });
  return new Response(new Uint8Array(png), { headers: { 'Content-Type': 'image/png' } });
};
