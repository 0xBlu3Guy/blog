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
 * Every tag the blog knows about. Each one gets a card on the tags page and its
 * own page, even before any post uses it (it then shows 0 posts). Tags used in
 * a post but missing here still appear. `devOnly` tags only show while running
 * `npm run dev`.
 */
export const tagList: { name: string; devOnly?: boolean }[] = [
  { name: 'Bug Bounty' },
  { name: 'CTF' },
  { name: 'Methodology' },
  { name: 'Thoughts' },
  { name: 'Vulnerability Research' },
  { name: 'Web Security' },
  { name: 'Reference', devOnly: true },
];
