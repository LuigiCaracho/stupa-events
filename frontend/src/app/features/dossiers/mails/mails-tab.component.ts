/**
 * I11 Mails: the mail templates of the dossier (documents of kind `mail_template`). The list on the left, the
 * template editor beside it (below it on a phone). The server never sends mail from the dossier.
 */
import { ChangeDetectionStrategy, Component, inject, input, output, signal } from '@angular/core';
import { rxResource } from '@angular/core/rxjs-interop';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { EmptyStateComponent } from '@shared/ui/empty-state/empty-state.component';
import { NoteComponent } from '@shared/ui/note/note.component';
import { SkeletonComponent } from '@shared/ui/skeleton/skeleton.component';
import { ButtonComponent } from '@stupa-makers/ui-kit';
import { catchError, of } from 'rxjs';
import type { EventDto } from '../api/event.models';
import { MailTemplatesApi } from '../api/mail-templates-api.service';
import type { MailTemplateOut } from '../model/document.models';
import { MailTemplateEditorComponent } from './mail-template-editor.component';

@Component({
  selector: 'app-mails-tab',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    TranslatePipe,
    ButtonComponent,
    EmptyStateComponent,
    MailTemplateEditorComponent,
    NoteComponent,
    SkeletonComponent,
  ],
  templateUrl: './mails-tab.component.html',
  styleUrl: './mails-tab.component.scss',
})
export class MailsTabComponent {
  private readonly api = inject(MailTemplatesApi);

  readonly event = input.required<EventDto>();
  readonly canEdit = input(false);

  readonly changed = output<void>();

  protected readonly list = rxResource({
    params: () => this.event().id,
    stream: ({ params }) => this.api.list(params),
  });
  protected readonly placeholders = rxResource({
    stream: () => this.api.placeholders().pipe(catchError(() => of([]))),
  });
  protected readonly selected = signal<MailTemplateOut | null>(null);
  protected readonly creating = signal(false);

  protected open(id: string): void {
    this.creating.set(false);
    this.api.get(this.event().id, id).subscribe((t) => this.selected.set(t));
  }

  protected create(): void {
    this.selected.set(null);
    this.creating.set(true);
  }

  protected saved(t: MailTemplateOut): void {
    this.creating.set(false);
    this.selected.set(t);
    this.list.reload();
    this.changed.emit();
  }
}
