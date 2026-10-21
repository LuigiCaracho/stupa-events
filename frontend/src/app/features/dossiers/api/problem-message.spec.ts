import { TestBed } from '@angular/core/testing';
import { I18nService } from '@core/i18n/i18n.service';
import { problemMessage } from './problem-message';

describe('problemMessage', () => {
  const i18n = () => TestBed.inject(I18nService);

  it('lists the missing fields of a refused publication', () => {
    const text = problemMessage(i18n(), {
      status: 422,
      code: 'publish_incomplete',
      reasons: [
        { code: 'field_missing', field: 'title' },
        { code: 'field_missing', field: 'starts_at' },
        { code: 'field_missing', field: 'organizationId' },
      ],
    });
    expect(text).toBe('Zum Veröffentlichen fehlt noch: Titel, Beginn, Organisation.');
  });

  it('maps known codes to fixed sentences', () => {
    expect(problemMessage(i18n(), { status: 409, code: 'conflict' })).toContain('Jemand anderes');
        expect(problemMessage(i18n(), { status: 413, code: 'payload_too_large' })).toContain('10 MiB');
  });

  it('maps the M5b codes to fixed sentences', () => {
    expect(problemMessage(i18n(), { status: 409, code: 'invalid_state' })).toContain(
      'aktuellen Zustand',
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
