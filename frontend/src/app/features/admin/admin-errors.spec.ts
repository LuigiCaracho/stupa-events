import { TestBed } from '@angular/core/testing';
import { I18nService } from '@core/i18n/i18n.service';
import { adminErrors } from './admin-errors';

const run = (problem: Parameters<typeof adminErrors>[1]) =>
  adminErrors(TestBed.inject(I18nService), problem);

describe('adminErrors', () => {
  it('puts a known code at its field', () => {
    expect(run({ status: 409, code: 'slug_taken' })).toEqual({
      fields: { slug: 'Slug schon vergeben.' },
      message: null,
    });
    expect(run({ status: 422, code: 'approver_requires_trusted' }).fields).toEqual({
      role: 'Approver nur in vertrauten Organisationen.',
    });
  });

  it('turns a rule without a field into a message', () => {
    expect(run({ status: 409, code: 'last_admin_mapping' }).message).toContain(
      'letzte Admin-Zuordnung',
    );
  });

  it('maps the organization cycle to the parent field', () => {
    expect(run({ status: 422, code: 'organization_cycle' }).fields).toEqual({
      parentId: 'Eine Organisation kann nicht unter sich selbst hängen.',
    });
  });

  it('shows a generic German text for an unmapped field error, never the server text', () => {
    expect(
      run({
        status: 422,
        code: 'validation_error',
        errors: [{ field: 'parentId', msg: 'unknown category' }],
      }),
    ).toEqual({ fields: { parentId: 'Ungültiger Wert.' }, message: null });
  });

  it('falls back to the generic problem text', () => {
    expect(run({ status: 403, code: 'forbidden' }).message).toBe(
      'Dafür fehlt dir die Berechtigung.',
    );
    expect(run({ status: 0 }).message).toBe('Keine Verbindung.');
  });
});
