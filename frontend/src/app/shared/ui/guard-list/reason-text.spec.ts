import { TestBed } from '@angular/core/testing';
import { I18nService } from '@core/i18n/i18n.service';
import { fieldLabel, reasonText } from './reason-text';

describe('reason-text', () => {
  const i18n = () => TestBed.inject(I18nService);

  it('translates known field names in both spellings', () => {
    expect(fieldLabel(i18n(), 'startsAt')).toBe('Beginn');
    expect(fieldLabel(i18n(), 'starts_at')).toBe('Beginn');
    expect(fieldLabel(i18n(), null)).toBe('');
  });

  it('keeps an unknown field name as it is', () => {
    expect(fieldLabel(i18n(), 'room_layout')).toBe('room_layout');
  });

  it('puts the field into the sentence', () => {
    const reason = {
      code: 'field_missing',
      field: 'summary',
      severity: 'blocker' as const,
      messageKey: 'guards.field_missing',
      fixAction: null,
    };
    expect(reasonText(i18n(), reason)).toBe('Es fehlt: Kurztext.');
  });
});
