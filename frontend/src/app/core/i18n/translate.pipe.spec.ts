/** Copied from STUPA-Workflow@93c33d6 frontend/src/app/core/i18n/translate.pipe.spec.ts (rewritten) */
/** Spec for the `t` pipe. */
import { TestBed } from '@angular/core/testing';
import { TranslatePipe } from './translate.pipe';

describe('TranslatePipe', () => {
  const pipe = (): TranslatePipe => TestBed.runInInjectionContext(() => new TranslatePipe());

  it('translates a key', () => {
    expect(pipe().transform('nav.events')).toBe('Events');
  });

  it('interpolates parameters', () => {
    expect(pipe().transform('shell.nav.brand', { name: 'STUPA Events' })).toBe(
      'STUPA Events, Start',
    );
  });
});
