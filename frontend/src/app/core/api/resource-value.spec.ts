import { signal } from '@angular/core';
import { resourceValue } from './resource-value';

const fake = (has: boolean, value?: number) =>
  ({ hasValue: () => has, value: signal(value) }) as never;

describe('resourceValue', () => {
  it('gives the value when there is one, even a falsy one', () => {
    expect(resourceValue(fake(true, 0), 5)).toBe(0);
    expect(resourceValue(fake(true, 3), 5)).toBe(3);
  });

  it('gives the fallback while there is none', () => {
    expect(resourceValue(fake(false), 5)).toBe(5);
  });
});
