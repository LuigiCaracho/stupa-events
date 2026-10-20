import { TestBed } from '@angular/core/testing';
import { I18nService } from '@core/i18n/i18n.service';
import { relativeDue } from './due-label';

describe('relativeDue', () => {
  const i18n = () => TestBed.inject(I18nService);

  it.each([
    [null, ''],
    [0, 'am Tag selbst'],
    [-28, '4 Wochen vorher'],
    [-7, '1 Woche vorher'],
    [-3, '3 Tage vorher'],
    [-1, '1 Tag vorher'],
    [14, '2 Wochen danach'],
    [2, '2 Tage danach'],
    [1, '1 Tag danach'],
    [7, '1 Woche danach'],
  ])('writes %s as "%s"', (offset, text) => {
    expect(relativeDue(i18n(), offset)).toBe(text);
  });
});
