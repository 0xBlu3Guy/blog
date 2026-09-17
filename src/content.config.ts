import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

/**
 * The content schema. Frontmatter is validated at build time, so a typo in a
 * post fails the build with a message naming the file and the field.
 */
const posts = defineCollection({
  loader: glob({ base: './src/content/posts', pattern: '**/*.{md,mdx}' }),
  schema: ({ image }) =>
    z.object({
      title: z.string().min(1),
      /** Optional: falls back to the post's first paragraph. */
      description: z.string().optional(),
      date: z.coerce.date(),
      tags: z.array(z.string().min(1)).default([]),
      /** Drafts are visible with `npm run dev`, excluded from builds. */
      draft: z.boolean().default(false),
      /** Optional social/share image, relative to the Markdown file. */
      image: image().optional(),
      imageAlt: z.string().optional(),
      author: z.string().optional(),
    }),
});

export const collections = { posts };
