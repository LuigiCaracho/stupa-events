/** The calendar subscription addresses of the Abos page: the `https` URL to copy and the `webcal` URL that opens the app. */

export interface SubscribeLinks {
  https: string;
  webcal: string;
}

/** Links for a path such as `/ics/all.ics` on the origin the visitor is on (never shortened, never rewritten). */
export function subscribeLinks(origin: string, path: string): SubscribeLinks {
  const https = `${origin}${path}`;
  return { https, webcal: https.replace(/^https?:/, 'webcal:') };
}

export const ALL_ICS = '/ics/all.ics';

export const categoryIcs = (slug: string): string => `/ics/k/${slug}.ics`;

/** The category slug of an anchor such as `#k=party`, or `null`. */
export function anchoredCategory(fragment: string | null): string | null {
  const m = /^k=([a-z0-9-]{1,80})$/.exec(fragment ?? '');
  return m ? m[1] : null;
}
