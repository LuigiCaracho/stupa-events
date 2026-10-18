import { formError, transitionBody } from './transition-request';

const base = {
  transition: 'T02' as const,
  note: '',
  immediate: true,
  publishDate: '',
  publishTime: '',
};

describe('transition request', () => {
  it('needs a note at the five transitions that ask for a reason', () => {
    for (const t of ['T03', 'T06', 'T07', 'T10', 'T11'] as const) {
      expect(formError({ ...base, transition: t })).toBe('noteRequired');
      expect(formError({ ...base, transition: t, note: '  ' })).toBe('noteRequired');
      expect(formError({ ...base, transition: t, note: 'Grund' })).toBeNull();
    }
    expect(formError(base)).toBeNull();
  });

  it('caps the note at 500 characters', () => {
    expect(formError({ ...base, note: 'x'.repeat(501) })).toBe('noteTooLong');
    expect(formError({ ...base, note: 'x'.repeat(500) })).toBeNull();
  });

  it('wants both parts of the release time at T04 or none; none without "sofort" only approves', () => {
    const t04 = { ...base, transition: 'T04' as const };
    expect(formError({ ...t04, immediate: false })).toBeNull();
    expect(formError({ ...t04, immediate: false, publishDate: '2026-11-01' })).toBe('publishAt');
    expect(formError({ ...t04, immediate: false, publishTime: '10:00' })).toBe('publishAt');
    expect(
      formError({ ...t04, immediate: false, publishDate: '2026-11-01', publishTime: '10:00' }),
    ).toBeNull();
    expect(formError({ ...t04, immediate: true })).toBeNull();
  });

  it('builds the body: trimmed note and the release time in UTC only for T04', () => {
    expect(transitionBody({ ...base, note: ' bitte ' })).toEqual({ note: 'bitte' });
    expect(transitionBody(base)).toEqual({});
    expect(
      transitionBody({
        ...base,
        transition: 'T04',
        immediate: false,
        publishDate: '2026-11-01',
        publishTime: '10:00',
      }),
    ).toEqual({ publishAt: '2026-11-01T09:00:00Z' });
    expect(
      transitionBody({
        ...base,
        transition: 'T04',
        publishDate: '2026-11-01',
        publishTime: '10:00',
      }),
    ).toEqual({});
  });
});
