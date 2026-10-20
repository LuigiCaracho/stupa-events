import { TestBed } from '@angular/core/testing';
import { I18nService } from '@core/i18n/i18n.service';
import { problemMessage } from './problem-message';

describe('problemMessage', () => {
  const i18n = () => TestBed.inject(I18nService);

  it('lists the blockers of a refused transition', () => {
    const text = problemMessage(i18n(), {
      status: 422,
      code: 'image_required',
      reasons: [
        {
          code: 'image_required',
          field: null,
          severity: 'blocker',
          messageKey: 'guards.image_required',
          fixAction: 'upload_poster',
        },
        {
          code: 'field_missing',
          field: 'venue_text',
          severity: 'blocker',
          messageKey: 'guards.field_missing',
          fixAction: 'fill_field',
        },
        {
          code: 'x',
          field: null,
          severity: 'warning',
          messageKey: 'guards.four_eyes',
          fixAction: null,
        },
      ],
    });
    expect(text).toBe('Nicht möglich: Poster fehlt oder ist nicht freigegeben. Es fehlt: Ort.');
  });

  it('maps known codes to fixed sentences', () => {
    expect(problemMessage(i18n(), { status: 409, code: 'conflict' })).toContain('Jemand anderes');
    expect(problemMessage(i18n(), { status: 409, code: 'field_locked' })).toContain('gesperrt');
    expect(problemMessage(i18n(), { status: 413, code: 'payload_too_large' })).toContain('10 MiB');
  });

  it('maps the M3 codes to fixed sentences', () => {
    expect(problemMessage(i18n(), { status: 422, code: 'reason_required' })).toBe(
      'Bitte gib einen Grund an.',
    );
    expect(problemMessage(i18n(), { status: 422, code: 'proposal_quota_exceeded' })).toContain(
      '5 offene Vorschläge',
    );
    expect(problemMessage(i18n(), { status: 403, code: 'four_eyes' })).toBe(
      'Eine andere Person muss freigeben.',
    );
    expect(problemMessage(i18n(), { status: 409, code: 'revert_poster_replaced' })).toContain(
      'Poster',
    );
  });

  it('adds the trace id to unknown errors', () => {
    expect(problemMessage(i18n(), { status: 500, traceId: 'abc123' })).toContain(
      'Fehler-ID: abc123',
    );
    expect(problemMessage(i18n(), { status: 500 })).toBe(
      'Das hat nicht geklappt. Bitte versuch es noch einmal.',
    );
  });

  it('reports a missing connection', () => {
    expect(problemMessage(i18n(), { status: 0 })).toBe('Keine Verbindung.');
  });

  it('falls back to the generic reason for an unknown message key', () => {
    const text = problemMessage(i18n(), {
      status: 422,
      reasons: [
        {
          code: 'z',
          field: null,
          severity: 'blocker',
          messageKey: 'guards.new_rule',
          fixAction: null,
        },
      ],
    });
    expect(text).toBe('Nicht möglich: Voraussetzung nicht erfüllt.');
  });
});

describe('problemMessage for the M4 codes', () => {
  const i18n = () => TestBed.inject(I18nService);

  it('names the limit of a file that is too large', () => {
    expect(
      problemMessage(i18n(), { status: 413, code: 'file_too_large', limitBytes: 10 * 1_048_576 }),
    ).toBe('Die Datei ist zu groß. Erlaubt sind 10 MB.');
    expect(problemMessage(i18n(), { status: 413, code: 'file_too_large' })).toContain('25 MB');
  });

  it('maps a few more codes to their sentence', () => {
    expect(problemMessage(i18n(), { status: 409, code: 'quote_expired' })).toBe(
      'Das Angebot ist abgelaufen.',
    );
    expect(problemMessage(i18n(), { status: 422, code: 'assignee_not_member' })).toBe(
      'Diese Person gehört nicht zur Organisation.',
    );
  });
});
