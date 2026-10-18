import { deadline } from './task-deadline';

const t = (key: string, params?: Record<string, string | number>) =>
  `${key}${params ? JSON.stringify(params) : ''}`;
const NOW = new Date('2026-11-01T12:00:00Z');

describe('deadline', () => {
  it.each([
    ['2026-11-01T11:00:00Z', 'error', 'tasks.dueNow'],
    ['2026-11-02T10:00:00Z', 'error', 'tasks.dueOne{"days":1}'],
    ['2026-11-03T10:00:00Z', 'error', 'tasks.dueDays{"days":2}'],
    ['2026-11-05T10:00:00Z', 'warn', 'tasks.dueDays{"days":4}'],
    ['2026-11-20T10:00:00Z', 'neutral', 'tasks.dueDays{"days":19}'],
  ])('%s is %s', (iso, kind, text) => {
    const d = deadline(iso, NOW, t as never);
    expect(d.kind).toBe(kind);
    expect(d.text).toBe(text);
  });
});
