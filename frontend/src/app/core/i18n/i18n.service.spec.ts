/** Copied from STUPA-Workflow@93c33d6 frontend/src/app/core/i18n/i18n.service.spec.ts (rewritten) */
/** Spec for the I18nService: German by default, English on demand, the choice remembered. */
import { TestBed } from '@angular/core/testing';
import { dateWords, setFormatLang } from './format-locale';
import { I18nService, toFormatLocale } from './i18n.service';

const browserLanguage = (value: string): void => {
  Object.defineProperty(window.navigator, 'language', { value, configurable: true });
};

describe('I18nService', () => {
  beforeEach(() => localStorage.clear());
  afterEach(() => {
    setFormatLang('de');
    document.documentElement.lang = 'de';
    jest.restoreAllMocks();
    browserLanguage('de-DE');
  });

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

  it('is ready at once and stays German when the saved choice says so', async () => {
    localStorage.setItem('ev.locale', 'de');
    await expect(service().ready()).resolves.toBeUndefined();
    expect(service().locale()).toBe('de');
  });

  it('follows an English browser on the first visit', async () => {
    browserLanguage('en-GB');
    const i18n = service();
    await i18n.ready();
    expect(i18n.locale()).toBe('en');
    expect(i18n.translate('public.nav.today')).toBe('Today');
    expect(i18n.formatLocale()).toBe('en-GB');
    expect(document.documentElement.lang).toBe('en');
    expect(dateWords().to).toBe('to');
  });

  it('switches on request, saves the choice and falls back to German for an internal key', async () => {
    const i18n = service();
    await i18n.setLocale('en');
    expect(i18n.translate('public.nav.search')).toBe('Search');
    expect(i18n.translate('nav.events')).toBe('Events');
    expect(i18n.translate('admin.save')).toBe('Speichern');
    expect(localStorage.getItem('ev.locale')).toBe('en');
    await i18n.setLocale('de');
    expect(i18n.translate('public.nav.search')).toBe('Suche');
  });

  it('prefers the saved choice over the browser language', async () => {
    localStorage.setItem('ev.locale', 'de');
    browserLanguage('en-GB');
    const i18n = service();
    await i18n.ready();
    expect(i18n.locale()).toBe('de');
  });

  it('works without storage', async () => {
    jest.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('blocked');
    });
    jest.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked');
    });
    const i18n = service();
    await i18n.ready();
    await expect(i18n.setLocale('en')).resolves.toBeUndefined();
    expect(i18n.locale()).toBe('en');
  });
});
