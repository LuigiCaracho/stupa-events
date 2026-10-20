/**
 * I27 part "Benachrichtigungen": two switches per notification kind, "In der App" and "Per Mail". A switch saves at
 * once with `PUT /account/notification-prefs` and falls back when the call fails. Essential kinds are locked and say
 * "Immer aktiv".
 */
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { rxResource } from '@angular/core/rxjs-interop';
import { problemOf } from '@core/api/problem';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import type { TranslationKey } from '@core/i18n/translations';
import { NoteComponent } from '@shared/ui/note/note.component';
import { SkeletonComponent } from '@shared/ui/skeleton/skeleton.component';
import { SwitchComponent, ToastService } from '@stupa-makers/ui-kit';
import { problemMessage } from '../../dossiers/api/problem-message';
import type { NotificationPref } from '../../dossiers/model/notification.models';
import { NotificationsApi } from '../../notifications/notifications-api.service';

type Channel = 'inApp' | 'mail';

@Component({
  selector: 'app-notification-prefs',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [TranslatePipe, NoteComponent, SkeletonComponent, SwitchComponent],
  templateUrl: './notification-prefs.component.html',
  styleUrl: './notification-prefs.component.scss',
})
export class NotificationPrefsComponent {
  private readonly api = inject(NotificationsApi);
  private readonly toast = inject(ToastService);
  private readonly i18n = inject(I18nService);

  protected readonly loaded = rxResource({ stream: () => this.api.prefs() });
  private readonly overrides = signal<Record<string, NotificationPref>>({});
  /** A switch keeps its own state after a click; a rollback renders the rows again so they show the stored value. */
  protected readonly rollbacks = signal(0);

  protected readonly prefs = computed<NotificationPref[]>(() =>
    (this.loaded.hasValue() ? this.loaded.value() : []).map((p) => this.overrides()[p.kind] ?? p),
  );

  protected label(kind: string): string {
    return this.i18n.translate(`notification.kind.${kind}` as TranslationKey);
  }

  protected set(pref: NotificationPref, channel: Channel, value: boolean): void {
    if (pref.essential || pref[channel] === value) return;
    const next = { ...pref, [channel]: value };
    this.overrides.update((o) => ({ ...o, [pref.kind]: next }));
    this.api.savePrefs([{ kind: pref.kind, inApp: next.inApp, mail: next.mail }]).subscribe({
      error: (err: unknown) => {
        this.overrides.update((o) => ({ ...o, [pref.kind]: pref }));
        this.rollbacks.update((n) => n + 1);
        this.toast.error(problemMessage(this.i18n, problemOf(err)));
      },
    });
  }
}
