import { makeEvent } from '../../../../testing/event-fixtures';
import { badLink, diff, editableFields, endBeforeStart, valueOf } from './form-model';

describe('form model', () => {
  const event = makeEvent({ summary: 'Film', venueId: 'v1', ticketUrl: null });

  it('shows the zoned wall clock of the event', () => {
    const value = valueOf(event);
    expect(value).toMatchObject({
      title: 'Movienight',
      startDate: '2026-11-05',
      startTime: '19:00',
      endTime: '22:00',
      venueId: 'v1',
    });
  });

  it('lays a draft over the event, including a cleared venue', () => {
    const value = valueOf(event, { summary: 'Neu', venueId: null, primaryCategoryId: 'c2' });
    expect(value).toMatchObject({ summary: 'Neu', venueId: '', primaryCategoryId: 'c2' });
  });

  it('lists every field as editable in idea and planning and none elsewhere without a server list', () => {
    expect(editableFields(makeEvent({ state: 'planning' }))).toContain('startsAt');
    expect(editableFields(makeEvent({ state: 'live' }))).toEqual([]);
    expect(editableFields(makeEvent({ editableFields: ['summary'] }))).toEqual(['summary']);
  });

  it('diffs only changed, editable fields and clears optional text with null', () => {
    const value = {
      ...valueOf(event),
      summary: 'Anders',
      costText: '5 €',
      venueText: '',
      title: '  Movienight  ',
    };
    expect(diff(event, value)).toEqual({ summary: 'Anders', costText: '5 €', venueText: null });
  });

  it('ignores a change of a locked field', () => {
    const live = makeEvent({ state: 'live', editableFields: ['summary'] });
    const value = { ...valueOf(live), summary: 'Korrektur', title: 'Hack', startTime: '23:00' };
    expect(diff(live, value)).toEqual({ summary: 'Korrektur' });
  });

  it('diffs the time, the venue and the category', () => {
    const value = {
      ...valueOf(event),
      startTime: '20:00',
      endDate: '2026-11-06',
      venueId: '',
      primaryCategoryId: 'c9',
    };
    expect(diff(event, value)).toEqual({
      startsAt: '2026-11-05T19:00:00Z',
      endsAt: '2026-11-06T21:00:00Z',
      venueId: null,
      primaryCategoryId: 'c9',
    });
  });

  it('refuses links without https and an end before the start', () => {
    expect(badLink('http://x.de')).toBe(true);
    expect(badLink('https://u@x.de')).toBe(true);
    expect(badLink('https://x.de/tickets')).toBe(false);
    expect(badLink('  ')).toBe(false);
    const value = { ...valueOf(event), endTime: '17:00' };
    expect(endBeforeStart(value, 'Europe/Berlin')).toBe(true);
    expect(endBeforeStart({ ...value, endTime: '' }, 'Europe/Berlin')).toBe(false);
  });
});

describe('form model details', () => {
  const event = makeEvent({
    summary: null,
    descriptionMd: null,
    costText: null,
    websiteUrl: null,
    venueText: null,
    primaryCategory: null,
  });

  it('shows missing optional values as empty fields', () => {
    expect(valueOf(event)).toMatchObject({
      summary: '',
      descriptionMd: '',
      costText: '',
      websiteUrl: '',
      venueText: '',
      primaryCategoryId: '',
      venueId: '',
    });
  });

  it('takes a cleared category from the draft', () => {
    expect(valueOf(makeEvent(), { primaryCategoryId: null }).primaryCategoryId).toBe('');
  });

  it('keeps a title that was only trimmed and never clears it to null', () => {
    expect(diff(event, { ...valueOf(event), title: '' })).toEqual({ title: '' });
    expect(diff(event, { ...valueOf(event), title: '  Movienight ' })).toEqual({});
  });

  it('does not diff an incomplete time', () => {
    expect(diff(event, { ...valueOf(event), startTime: '', endDate: '' })).toEqual({});
  });

  it('sets a venue and a category that the event did not have', () => {
    expect(diff(event, { ...valueOf(event), venueId: 'v2', primaryCategoryId: 'c2' })).toEqual({
      venueId: 'v2',
      primaryCategoryId: 'c2',
    });
  });
});
