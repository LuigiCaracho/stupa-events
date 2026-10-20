/** The local copy of an unsaved text (contract 6.2): `localStorage`, every access in try/catch, never required. */
const key = (docKey: string): string => `stupa-events:draft:${docKey}`;

export function readLocalCopy(docKey: string): string | null {
  try {
    return localStorage.getItem(key(docKey));
  } catch {
    return null;
  }
}

export function writeLocalCopy(docKey: string, text: string): void {
  try {
    localStorage.setItem(key(docKey), text);
  } catch {
    /* storage blocked or full: the server draft still runs */
  }
}

export function clearLocalCopy(docKey: string): void {
  try {
    localStorage.removeItem(key(docKey));
  } catch {
    /* nothing to clear */
  }
}
