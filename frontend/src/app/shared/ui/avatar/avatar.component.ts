/** Copied from STUPA-Workflow@93c33d6 frontend/src/app/shared/ui/avatar/avatar.component.ts (rewritten) */
import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

/** The size of an avatar: 40px (`md`), 32px (`sm`) or 22px (`xs`, in a dense tile). */
export type AvatarSize = 'md' | 'sm' | 'xs';

/**
 * The initials of a name: the first letter of the first and of the last word.
 *
 * "Mara Keller" gives "MK", "Paul" gives "P". Words in brackets do not count.
 */
export function initials(name: string): string {
  const words = name
    .replace(/\(.*?\)/g, ' ')
    .split(/\s+/)
    .map((w) => w.replace(/^[^\p{L}\p{N}]+/u, ''))
    .filter((w) => w.length > 0);
  if (words.length === 0) return '?';
  const first = [...words[0]][0];
  const last = words.length > 1 ? [...words[words.length - 1]][0] : '';
  return (first + last).toLocaleUpperCase();
}

/**
 * The initials of a person in a circle. Rewritten from the workflow tool: no Gravatar proxy, the
 * initials only. The full name is the accessible name and the tooltip; set `decorative` when
 * the name stands next to the avatar.
 */
@Component({
  selector: 'app-avatar',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    '[class.av--sm]': "size() === 'sm'",
    '[class.av--xs]': "size() === 'xs'",
    '[class.av--accent]': 'accent()',
    '[attr.role]': "decorative() ? null : 'img'",
    '[attr.aria-label]': 'decorative() ? null : name()',
    '[attr.aria-hidden]': "decorative() ? 'true' : null",
    '[attr.title]': 'name()',
  },
  templateUrl: './avatar.component.html',
  styleUrl: './avatar.component.scss',
})
export class AvatarComponent {
  readonly name = input.required<string>();
  readonly size = input<AvatarSize>('md');
  readonly accent = input(false);
  readonly decorative = input(false);
  /** Kept for the copied filter chip; the initials need no principal id. */
  readonly principalId = input<string | null | undefined>(null);

  protected readonly letters = computed(() => initials(this.name()));
}
