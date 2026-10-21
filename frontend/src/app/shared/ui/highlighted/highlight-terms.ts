/**
 * Marks the words of a query inside a plain text, for hits without a full-text part (typo matches carry no server
 * highlight, M5 contract 6.1). Pattern from STUPA-Workflow@93c33d6 frontend/src/app/features/search/highlight.ts
 * (rewritten, no code copied). Case-insensitive; words shorter than two characters are ignored. A title word of at least
 * five letters that sits inside a query word is marked too, the way the server finds compounds ("Fachschaftssitzung"
 * finds "Sitzung", contract 6.2).
 */
import type { TextSegment } from './highlighted.component';

const COMPOUND_MIN = 5;
const escape = (word: string): string => word.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
const fold = (word: string): string => word.normalize('NFD').replace(/\p{M}/gu, '').toLowerCase();

function compoundParts(text: string, words: readonly string[]): string[] {
  const folded = words.map(fold);
  return (text.match(/[\p{L}\p{N}]+/gu) ?? []).filter(
    (part) =>
      part.length >= COMPOUND_MIN && folded.some((w) => w !== fold(part) && w.includes(fold(part))),
  );
}

export function highlightTerms(text: string, query: string): TextSegment[] {
  const words = query
    .split(/\s+/)
    .map((w) => w.replace(/^["-]+|"+$/g, ''))
    .filter((w) => w.length >= 2);
  if (words.length === 0) return [{ text, hit: false }];
  const terms = [...words, ...compoundParts(text, words)].sort((a, b) => b.length - a.length);
  const pattern = new RegExp(`(${terms.map(escape).join('|')})`, 'giu');
  return text
    .split(pattern)
    .map((part, i) => ({ text: part, hit: i % 2 === 1 }))
    .filter((segment) => segment.text !== '');
}
