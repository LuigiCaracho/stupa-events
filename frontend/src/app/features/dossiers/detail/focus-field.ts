/** Moves the focus to the form control that a guard fix button names ("Ergänzen", "Datum ändern", "Ort wählen"). */
import type { FixAction } from '@core/api/models';

const CONTROL: Record<string, string> = {
  startsAt: 'startDate',
  endsAt: 'endDate',
  organizationId: 'title',
};

/** The form control name for a fix action and the field of its reason. */
export function controlFor(action: FixAction, field: string | null): string {
  if (action === 'change_date') return 'startDate';
  if (action === 'set_end') return 'endDate';
  if (action === 'pick_venue') return 'venueId';
  if (action === 'mark_cancellation') return 'title';
  const camel = (field ?? 'title').replace(/_([a-z])/g, (_m, c: string) => c.toUpperCase());
  return CONTROL[camel] ?? camel;
}

/** Scrolls the control into view and focuses its first focusable part; returns whether it found one. */
export function focusField(root: HTMLElement, action: FixAction, field: string | null): boolean {
  const name = controlFor(action, field);
  const target = root.querySelector<HTMLElement>(
    `[formcontrolname="${name}"] input, [formcontrolname="${name}"] button, [formcontrolname="${name}"] textarea`,
  );
  target?.scrollIntoView?.({ block: 'center' });
  target?.focus();
  return !!target;
}
