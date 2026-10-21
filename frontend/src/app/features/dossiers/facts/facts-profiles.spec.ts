import { fieldsOf, formFromFacts, toFacts } from './facts-profiles';

describe('facts profiles', () => {
  it('has the fields of the profile, generic as the fallback', () => {
    expect(fieldsOf('party').map((f) => f.key)).toEqual([
      'ageLimit', 'capacity', 'securityPlanDone', 'noisePermitRef', 'budgetCents',
    ]);
    expect(fieldsOf(undefined)).toBe(fieldsOf('generic'));
    expect(fieldsOf('trip').map((f) => f.key)).toContain('signupDeadline');
  });

  it('turns the stored facts into form text and cents into euros', () => {
    expect(formFromFacts('party', { ageLimit: 16, securityPlanDone: true, budgetCents: 12050 })).toEqual({
      ageLimit: '16', capacity: '', securityPlanDone: true, noisePermitRef: '', budgetCents: '120.50',
    });
    expect(formFromFacts('generic', null)).toEqual({ capacity: '', budgetCents: '' });
  });

  it('leaves out empty fields and false ticks', () => {
    expect(
      toFacts('party', { ageLimit: '18', capacity: '', securityPlanDone: false, noisePermitRef: ' ', budgetCents: '10' }),
    ).toEqual({ ok: true, facts: { ageLimit: 18, budgetCents: 1000 } });
  });

  it('keeps zero as a value (age limit 0)', () => {
    expect(toFacts('party', { ageLimit: '0' })).toEqual({ ok: true, facts: { ageLimit: 0 } });
  });

  it('refuses text where a number belongs, an http link and a reversed range', () => {
    expect(toFacts('generic', { capacity: 'viele', budgetCents: '-3' })).toEqual({
      ok: false,
      errors: { capacity: 'facts.errNumber', budgetCents: 'facts.errNumber' },
    });
    expect(toFacts('trip', { signupUrl: 'http://x.de' })).toEqual({
      ok: false,
      errors: { signupUrl: 'facts.errUrl' },
    });
    expect(toFacts('trip', { minParticipants: '12', maxParticipants: '8' })).toEqual({
      ok: false,
      errors: { maxParticipants: 'facts.errRange' },
    });
  });

  it('accepts a valid trip', () => {
    expect(
      toFacts('trip', {
        meetingPoint: 'Hbf', minParticipants: '8', maxParticipants: '12',
        signupUrl: 'https://anmeldung.example/davos', signupDeadline: '2026-12-01', priceText: '120 €',
      }),
    ).toEqual({
      ok: true,
      facts: {
        meetingPoint: 'Hbf', minParticipants: 8, maxParticipants: 12,
        signupUrl: 'https://anmeldung.example/davos', signupDeadline: '2026-12-01T22:59:00Z', priceText: '120 €',
      },
    });
  });

  it('shows a stored sign-up deadline as the local day', () => {
    expect(formFromFacts('trip', { signupDeadline: '2026-12-01T22:59:00Z' })['signupDeadline']).toBe('2026-12-01');
    expect(formFromFacts('trip', { signupDeadline: '2026-06-01T21:59:00Z' })['signupDeadline']).toBe('2026-06-01');
  });

  it('takes the quorum as a number', () => {
    expect(toFacts('meeting', { quorumNeeded: '5' })).toEqual({ ok: true, facts: { quorumNeeded: 5 } });
  });
});
