/** Client-side line diff for long text fields of two event revisions (the server diff exists for documents only). */
import type { DiffLine, DiffOut } from '../model/document.models';

const MAX_LINES = 2000;

export function lineDiff(from: string, to: string, fromRev = 0, toRev = 0): DiffOut | null {
  const a = from.split('\n');
  const b = to.split('\n');
  if (a.length > MAX_LINES || b.length > MAX_LINES) return null;
  const table = Array.from({ length: a.length + 1 }, () => new Array<number>(b.length + 1).fill(0));
  for (let i = a.length - 1; i >= 0; i--)
    for (let j = b.length - 1; j >= 0; j--)
      table[i][j] =
        a[i] === b[j] ? table[i + 1][j + 1] + 1 : Math.max(table[i + 1][j], table[i][j + 1]);
  const lines: DiffLine[] = [];
  let i = 0;
  let j = 0;
  while (i < a.length || j < b.length) {
    if (i < a.length && j < b.length && a[i] === b[j]) {
      lines.push({ op: 'equal', text: a[i], fromLine: i + 1, toLine: j + 1 });
      i++;
      j++;
    } else if (j >= b.length || (i < a.length && table[i + 1][j] >= table[i][j + 1])) {
      lines.push({ op: 'remove', text: a[i], fromLine: i + 1, toLine: null });
      i++;
    } else {
      lines.push({ op: 'add', text: b[j], fromLine: null, toLine: j + 1 });
      j++;
    }
  }
  return {
    from: fromRev,
    to: toRev,
    lines,
    added: lines.filter((l) => l.op === 'add').length,
    removed: lines.filter((l) => l.op === 'remove').length,
  };
}
