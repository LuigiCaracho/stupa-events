import { TestBed } from '@angular/core/testing';
import type { ProblemReason } from '@core/api/models';
import { I18nService } from '@core/i18n/i18n.service';
import { MAILTO_LIMIT, mailtoFor, templateReasonText } from './mail-preview';

describe('mailtoFor', () => {
  it('encodes subject and body', () => {
    expect(mailtoFor('Hallo Welt', 'a&b\nc')).toEqual({
      href: 'mailto:?subject=Hallo%20Welt&body=a%26b%0Ac',
    });
  });

  it('asks to copy above the length limit', () => {
    expect(mailtoFor('s', 'x'.repeat(MAILTO_LIMIT))).toEqual({ tooLong: true });
  });
});

describe('templateReasonText', () => {
  const reason = (r: Partial<ProblemReason> & { allowed?: string[]; line?: number }) =>
    ({ severity: 'blocker', messageKey: '', fixAction: null, field: null, ...r }) as ProblemReason;
  const i18n = () => TestBed.inject(I18nService);

  it('lists the allowed placeholders', () => {
    expect(
      templateReasonText(
        i18n(),
        reason({
          code: 'unknown_placeholder',
          field: 'event.raum',
          allowed: ['event.title', 'org.name'],
        }),
      ),
    ).toBe(
      'Unbekannter Platzhalter {{ event.raum }}. Erlaubt sind: {{ event.title }}, {{ org.name }}',
    );
    expect(templateReasonText(i18n(), reason({ code: 'unknown_placeholder' }))).toContain(
      'Erlaubt sind: ',
    );
  });

  it('names statements, syntax errors and anything else', () => {
    expect(templateReasonText(i18n(), reason({ code: 'statement_not_allowed' }))).toContain(
      'nicht erlaubt',
    );
    expect(templateReasonText(i18n(), reason({ code: 'syntax_error', line: 3 }))).toBe(
      'Syntaxfehler in Zeile 3.',
    );
    expect(templateReasonText(i18n(), reason({ code: 'syntax_error' }))).toBe(
      'Syntaxfehler in Zeile 0.',
    );
    expect(templateReasonText(i18n(), reason({ code: 'other' }))).toContain('unzulässige');
  });
});
