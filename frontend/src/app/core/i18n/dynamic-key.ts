/** Looks up a translation key that is built from a server value (`clone.part.<part>`); an unknown value gives `null`. */
import { de, type TranslationKey } from './translations';

export function dynamicKey(prefix: string, name: string | null | undefined): TranslationKey | null {
  if (!name) return null;
  const key = `${prefix}.${name.replace(/([A-Z])/g, '_$1').replace(/-/g, '_').toLowerCase()}`;
  return key in de ? (key as TranslationKey) : null;
}
