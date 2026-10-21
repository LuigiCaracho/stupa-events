import { type CancelForm, cancelBody, cancelError } from './cancel-request';

const NOW = new Date('2026-10-18T10:00:00Z');
const form: CancelForm = {
  mode: 'cancel',
  reason: 'Referent krank',
  code: 'illness',
  publicText: '',
  newDate: '',
  newTime: '',
  tzid: 'Europe/Berlin',
  now: NOW,
};

describe('cancel request', () => {
  it('needs no internal reason but caps it at 500 characters', () => {
    expect(cancelError({ ...form, reason: '' })).toBeNull();
    expect(cancelError({ ...form, reason: 'x'.repeat(501) })).toBe('reasonLong');
    expect(cancelError(form)).toBeNull();
  });

  it('caps the public text at 140 characters', () => {
    expect(cancelError({ ...form, publicText: 'x'.repeat(141) })).toBe('publicText');
  });

  it('wants a complete new date in the future when postponing with one', () => {
    const postpone = { ...form, mode: 'postpone' as const };
    expect(cancelError(postpone)).toBeNull();
    expect(cancelError({ ...postpone, newDate: '2026-11-01' })).toBe('newDate');
    expect(cancelError({ ...postpone, newDate: '2026-10-01', newTime: '10:00' })).toBe('newDate');
    expect(cancelError({ ...postpone, newDate: '2026-11-01', newTime: '10:00' })).toBeNull();
  });

  it('builds the cancel body and leaves empty texts out', () => {
    expect(cancelBody({ ...form, publicText: ' Krank ' })).toEqual({
      reason: 'Referent krank',
      publicReasonCode: 'illness',
      publicReasonText: 'Krank',
    });
    expect(cancelBody({ ...form, reason: ' ' })).toEqual({ publicReasonCode: 'illness' });
  });

  it('adds the new start in UTC only when postponing with a date', () => {
    const postpone = {
      ...form,
      mode: 'postpone' as const,
      newDate: '2026-11-01',
      newTime: '10:00',
    };
    expect(cancelBody(postpone)).toMatchObject({ newStartsAt: '2026-11-01T09:00:00Z' });
    expect(cancelBody({ ...postpone, mode: 'cancel' })).not.toHaveProperty('newStartsAt');
    expect(cancelBody({ ...postpone, newDate: '' })).not.toHaveProperty('newStartsAt');
  });

  it('sends only the note when the event is put back on', () => {
    expect(cancelBody({ ...form, mode: 'reinstate' })).toEqual({ reason: 'Referent krank' });
    expect(cancelBody({ ...form, mode: 'reinstate', reason: '' })).toEqual({});
  });
});
