/**
 * I28 Inbox: the side sheet behind the bell. Each entry shows its kind as text, the dossier, the relative time and, when
 * unread, a dot and bold type (never only colour). A click marks it read and goes to the link of the notification.
 */
import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { Router } from '@angular/router';
import { I18nService } from '@core/i18n/i18n.service';
import { LocalizedDatePipe } from '@core/i18n/localized-date.pipe';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import type { TranslationKey } from '@core/i18n/translations';
import { NoteComponent } from '@shared/ui/note/note.component';
import { SideSheetComponent } from '@shared/ui/side-sheet/side-sheet.component';
import { SkeletonComponent } from '@shared/ui/skeleton/skeleton.component';
import { ButtonComponent } from '@stupa-makers/ui-kit';
import type { NotificationOut } from '../dossiers/model/notification.models';
import { NotificationsStore } from './notifications.store';

@Component({
  selector: 'app-inbox',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    LocalizedDatePipe,
    TranslatePipe,
    ButtonComponent,
    NoteComponent,
    SideSheetComponent,
    SkeletonComponent,
  ],
  templateUrl: './inbox.component.html',
  styleUrl: './inbox.component.scss',
})
export class InboxComponent {
  protected readonly store = inject(NotificationsStore);
  private readonly router = inject(Router);
  private readonly i18n = inject(I18nService);

  protected kind(item: NotificationOut): string {
    return this.i18n.translate(`notification.kind.${item.kind}` as TranslationKey);
  }

  protected go(item: NotificationOut): void {
    this.store.markRead(item);
    this.store.open.set(false);
    if (item.link) void this.router.navigateByUrl(item.link);
  }
}
