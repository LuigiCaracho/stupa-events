/** Relative text of a checklist due date from its offset to the start ("4 Wochen vorher", "Am Tag", "2 Tage danach"). */
import type { I18nService } from '@core/i18n/i18n.service';

export function relativeDue(i18n: I18nService, offsetDays: number | null): string {
  if (offsetDays === null) return '';
  if (offsetDays === 0) return i18n.translate('checklist.dueSameDay');
  const days = Math.abs(offsetDays);
  const weeks = days % 7 === 0;
  const count = weeks ? days / 7 : days;
  const unit = weeks ? (count === 1 ? 'week' : 'weeks') : count === 1 ? 'day' : 'days';
  const when = offsetDays < 0 ? 'before' : 'after';
  return i18n.translate(`checklist.due.${unit}.${when}`, { count });
}
