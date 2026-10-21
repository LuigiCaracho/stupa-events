/** Moves the focus to the form control that a hint names ("Es fehlt der Ort", "Es fehlt ein Kurztext"). */

const CONTROL: Record<string, string> = {
  startsAt: 'startDate',
  endsAt: 'endDate',
  venue: 'venueId',
  category: 'primaryCategoryId',
};

/** The form control name for the field of a hint; a field without its own control gives the title. */
export function controlFor(field: string | null): string {
  const camel = (field ?? 'title').replace(/_([a-z])/g, (_m, c: string) => c.toUpperCase());
  return CONTROL[camel] ?? camel;
}

/** Scrolls the control into view and focuses its first focusable part; returns whether it found one. */
export function focusField(root: HTMLElement, field: string | null): boolean {
  const name = controlFor(field);
  const target = root.querySelector<HTMLElement>(
    `[formcontrolname="${name}"] input, [formcontrolname="${name}"] button, [formcontrolname="${name}"] textarea`,
  );
  target?.scrollIntoView?.({ block: 'center' });
  target?.focus();
  return !!target;
}
