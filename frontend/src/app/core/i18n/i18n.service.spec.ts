/** Copied from STUPA-Workflow@93c33d6 frontend/src/app/core/i18n/i18n.service.spec.ts (rewritten) */
/** Spec for the DE-only I18nService. */
import { TestBed } from '@angular/core/testing';
import { I18nService, toFormatLocale } from './i18n.service';

describe('I18nService', () => {
  const service = (): I18nService => TestBed.inject(I18nService);

  it('defaults to German and sets <html lang>', () => {
    expect(service().locale()).toBe('de');
    expect(document.documentElement.lang).toBe('de');
  });

  it('translates a key and interpolates parameters', () => {
    const i18n = service();
    expect(i18n.translate('nav.events')).toBe('Events');
    expect(i18n.translate('shell.nav.brand', { name: 'X' })).toBe('X, Start');
    expect(i18n.translate('shell.nav.brand', {})).toBe('{name}, Start');
  });

  it('falls back to the key itself for an unknown key', () => {
    expect(service().translate('does.not.exist' as never)).toBe('does.not.exist');
  });

  it('maps every locale to a German Intl tag', () => {
    expect(toFormatLocale('de')).toBe('de-DE');
    expect(toFormatLocale('xx')).toBe('de-DE');
    expect(service().formatLocale()).toBe('de-DE');
  });

  it('is ready at once', async () => {
    await expect(service().ready()).resolves.toBeUndefined();
  });
});
