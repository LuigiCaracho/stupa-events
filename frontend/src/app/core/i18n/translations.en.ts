/** The English catalog of the public site, assembled from its parts. Loaded on demand, see `loadEnglish`. */
import { mapEn } from './translations.map.en';
import { publicEn } from './translations.public.en';
import { sharedEn } from './translations.shared.en';
import { shellEn } from './translations.shell.en';
import { subscriptionsEn } from './translations.subscriptions.en';

export const en = {
  ...shellEn,
  ...sharedEn,
  ...publicEn,
  ...subscriptionsEn,
  ...mapEn,
} as const;
