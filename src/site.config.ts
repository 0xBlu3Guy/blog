/**
 * Everything personal about the site lives here.
 * Edit this file, not the components.
 */
export const site = {
  title: '0xBlu3Guy',
  /** Used in <meta name="author">, the RSS feed and the footer. */
  author: '0xBlu3Guy',
  description: 'My safe corner of the internet.',
  /** BCP-47 language tag for <html lang> and the RSS feed. */
  lang: 'en',
  /** Shown on the About page and used for the contact links. */
  email: 'sobhanhosseinpour@protonmail.com',
  social: {
    github: 'https://github.com/0xBlu3Guy',
    telegram: 'https://t.me/SobhanHosseinpour',
    /** Set to a URL to show a LinkedIn link, or leave empty to hide it. */
    linkedin: 'https://www.linkedin.com/in/sobhan-hosseinpour',
  },
} as const;

/**
 * Optional one-line blurbs shown at the top of a tag page (/tags/<slug>).
 * Keys are tag slugs. Tags without an entry simply show the post count.
 * This is entirely optional: tag pages are generated from post frontmatter,
 * never from this list.
 */
export const tagDescriptions: Record<string, string> = {
  ctf: "Posts about CTFs, challenges, writeups and things I've learned.",
  'bug-bounty': 'Recon, methodology and writeups from bug bounty hunting.',
  'web-security': 'Attacking and defending web applications.',
  security: 'General security notes, tooling and defensive work.',
  thoughts: 'Less technical posts: reflections on the journey.',
  methodology: 'How I organise work, take notes and stay repeatable.',
  career: 'Learning, growth and working in this field.',
  cybersecurity: 'Broad security topics that cut across disciplines.',
};
