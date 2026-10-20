import { lineDiff } from './line-diff';

describe('lineDiff', () => {
  it('marks equal, added and removed lines with their numbers', () => {
    const diff = lineDiff('a\nb\nc', 'a\nc\nd', 1, 2);
    expect(diff?.lines.map((l) => [l.op, l.text])).toEqual([
      ['equal', 'a'],
      ['remove', 'b'],
      ['equal', 'c'],
      ['add', 'd'],
    ]);
    expect(diff).toMatchObject({ from: 1, to: 2, added: 1, removed: 1 });
    expect(diff?.lines[2]).toMatchObject({ fromLine: 3, toLine: 2 });
  });

  it('handles an empty side', () => {
    expect(lineDiff('', 'x')?.added).toBe(1);
    expect(lineDiff('x', '')?.removed).toBe(1);
  });

  it('gives up above the line limit', () => {
    const big = Array.from({ length: 2001 }, (_, i) => String(i)).join('\n');
    expect(lineDiff(big, 'x')).toBeNull();
  });
});
