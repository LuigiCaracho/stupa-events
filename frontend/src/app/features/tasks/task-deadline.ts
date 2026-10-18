/** The traffic light of a due date: "in 3 Tagen" in the colour that fits how close it is. */
import type { TranslationKey } from '@core/i18n/translations';
import type { StatusKind } from '@shared/status-kind.util';

const DAY_MS = 86_400_000;
const URGENT_DAYS = 2;
const SOON_DAYS = 7;

export interface Deadline {
  kind: StatusKind;
  text: string;
  days: number;
}

type Translate = (key: TranslationKey, params?: Record<string, string | number>) => string;

/** Whole days from `now` to `iso` (negative once it has begun); the colour follows the days left. */
export function deadline(iso: string, now: Date, translate: Translate): Deadline {
  const days = Math.ceil((Date.parse(iso) - now.getTime()) / DAY_MS);
  const kind: StatusKind = days <= URGENT_DAYS ? 'error' : days <= SOON_DAYS ? 'warn' : 'neutral';
  if (days <= 0) return { kind: 'error', text: translate('tasks.dueNow'), days };
  return { kind, text: translate(days === 1 ? 'tasks.dueOne' : 'tasks.dueDays', { days }), days };
}
