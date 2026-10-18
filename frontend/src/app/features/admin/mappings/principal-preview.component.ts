/**
 * I24 preview "Wer bekommt was": the people whose cached IdP groups contain a mapped group,
 * with their last login and open sessions, and the admin button "Sitzungen widerrufen" per person.
 */
import { ChangeDetectionStrategy, Component, inject, input, signal } from '@angular/core';
import { rxResource } from '@angular/core/rxjs-interop';
import { problemOf } from '@core/api/problem';
import { I18nService } from '@core/i18n/i18n.service';
import { LocalizedDatePipe } from '@core/i18n/localized-date.pipe';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { NoteComponent } from '@shared/ui/note/note.component';
import { ButtonComponent, DialogComponent, ToastService } from '@stupa-makers/ui-kit';
import { problemMessage } from '../../dossiers/api/problem-message';
import type { AdminPrincipal } from '../api/admin.models';
import { MappingsApi } from '../api/mappings-api.service';
import { SessionsApi } from '../api/sessions-api.service';

@Component({
  selector: 'app-principal-preview',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [TranslatePipe, LocalizedDatePipe, ButtonComponent, DialogComponent, NoteComponent],
  templateUrl: './principal-preview.component.html',
  styleUrl: './principal-preview.component.scss',
})
export class PrincipalPreviewComponent {
  private readonly mappings = inject(MappingsApi);
  private readonly sessions = inject(SessionsApi);
  private readonly toast = inject(ToastService);
  private readonly i18n = inject(I18nService);

  readonly group = input.required<string>();

  protected readonly people = rxResource({
    params: () => this.group(),
    stream: ({ params }) => this.mappings.principals(params),
  });
  protected readonly target = signal<AdminPrincipal | null>(null);
  protected readonly busy = signal(false);

  protected confirm(): void {
    const person = this.target();
    if (!person || this.busy()) return;
    this.busy.set(true);
    this.sessions.revokePrincipal(person.id).subscribe({
      next: ({ revoked }) => {
        this.busy.set(false);
        this.target.set(null);
        this.toast.success(this.i18n.translate('admin.sessionsRevoked', { n: revoked }));
        this.people.reload();
      },
      error: (err: unknown) => {
        this.busy.set(false);
        this.toast.error(problemMessage(this.i18n, problemOf(err)));
      },
    });
  }
}
