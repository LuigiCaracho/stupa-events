import { formFromOutcome, toOutcomeIn, type OutcomeFormValue } from './outcome-model';

const form = (over: Partial<OutcomeFormValue> = {}): OutcomeFormValue => ({
  attendance: '',
  costs: '',
  revenue: '',
  notes: '',
  waived: false,
  waivedReason: '',
  ...over,
});

describe('outcome model', () => {
  it('shows stored cents as euros and empty fields for no outcome', () => {
    expect(formFromOutcome(null)).toEqual(form());
    expect(
      formFromOutcome({
        attendance: 87,
        costsCents: 24500,
        revenueCents: 0,
        notes: 'x',
        waived: false,
        waivedReason: null,
      }),
    ).toEqual(form({ attendance: '87', costs: '245.00', revenue: '0.00', notes: 'x' }));
  });

  it('sends euros as cents and keeps zero as a value', () => {
    expect(toOutcomeIn(form({ attendance: '87', costs: '245.5', revenue: '0' }))).toEqual({
      ok: true,
      body: { attendance: 87, costsCents: 24550, revenueCents: 0, notes: null, waived: false, waivedReason: null },
    });
  });

  it('leaves empty numbers as null', () => {
    expect(toOutcomeIn(form({ notes: ' Gut ' }))).toEqual({
      ok: true,
      body: { attendance: null, costsCents: null, revenueCents: null, notes: 'Gut', waived: false, waivedReason: null },
    });
  });

  it('refuses a fraction of a person, a negative amount and non-numbers', () => {
    const bad = toOutcomeIn(form({ attendance: '2.5', costs: '-1', revenue: 'abc' }));
    expect(bad).toEqual({
      ok: false,
      errors: { attendance: 'outcome.errAttendance', costs: 'outcome.errAmount', revenue: 'outcome.errAmount' },
    });
  });

  it('needs a reason of ten characters to waive and clears the numbers', () => {
    expect(toOutcomeIn(form({ waived: true, waivedReason: 'zu kurz', attendance: '5' }))).toEqual({
      ok: false,
      errors: { waivedReason: 'outcome.waiverReason' },
    });
    expect(toOutcomeIn(form({ waived: true, waivedReason: 'Kein Eintritt, keine Kosten', attendance: '5', costs: '3' }))).toEqual({
      ok: true,
      body: {
        attendance: null, costsCents: null, revenueCents: null, notes: null,
        waived: true, waivedReason: 'Kein Eintritt, keine Kosten',
      },
    });
  });

  it('limits the notes to 2000 characters', () => {
    expect(toOutcomeIn(form({ notes: 'x'.repeat(2001) }))).toMatchObject({ ok: false });
  });
});
