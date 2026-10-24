/**
 * The calendar address of a profile: a `webcal:` button that opens the calendar app, the `https` address in a read-only
 * field with a copy button, and the hints for Google and for the delay. Shown once on the result of Get started and
 * after a new address was made; the address is never stored by the page.
 */
import { ChangeDetectionStrategy, Component, inject, input, signal } from '@angular/core';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { NoteComponent } from '@shared/ui/note/note.component';
import { ButtonComponent, ToastService } from '@stupa-makers/ui-kit';
import { LinkButtonComponent } from '../link-button/link-button.component';
import { ShareService } from '../share.service';

let nextId = 0;

@Component({
  selector: 'app-profile-links',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [TranslatePipe, ButtonComponent, LinkButtonComponent, NoteComponent],
  templateUrl: './profile-links.component.html',
  styleUrl: './profile-links.component.scss',
})
export class ProfileLinksComponent {
  private readonly share = inject(ShareService);
  private readonly toast = inject(ToastService);
  private readonly i18n = inject(I18nService);

  readonly icsUrl = input.required<string>();
  readonly webcalUrl = input.required<string>();
  protected readonly copyFailed = signal(false);
  protected readonly fieldId = `profile-url-${nextId++}`;

  protected async copy(): Promise<void> {
    const ok = await this.share.copy(this.icsUrl());
    this.copyFailed.set(!ok);
    if (ok) this.toast.success(this.i18n.translate('public.links.copied'));
  }
}
