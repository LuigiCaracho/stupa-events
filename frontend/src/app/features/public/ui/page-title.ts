/** Sets the browser tab title of a public page ("<Name> · STUPA Events") while the page lives; call it in an injection context. */
import { effect, inject } from '@angular/core';
import { Title } from '@angular/platform-browser';

export const SITE_NAME = 'STUPA Events';

/** `name` is read reactively, so a title that arrives with the data (an event) updates the tab. `null` keeps the site name. */
export function usePageTitle(name: () => string | null): void {
  const title = inject(Title);
  effect(() => {
    const value = name();
    title.setTitle(value ? `${value} · ${SITE_NAME}` : SITE_NAME);
  });
}
