/** I15: dialog "Ausnahme ohne Bild" (editorial staff only). Grants the exception for one event. */
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  input,
  output,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { problemOf } from '@core/api/problem';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { NoteComponent } from '@shared/ui/note/note.component';
import {
  ButtonComponent,
  DialogComponent,
  InputComponent,
  ToastService,
} from '@stupa-makers/ui-kit';
import type { EventDto } from '../api/event.models';
import { EventsApi } from '../api/events-api.service';
import { problemMessage } from '../api/problem-message';

const MIN_REASON = 10;

@Component({
  selector: 'app-image-exception-dialog',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    FormsModule,
    TranslatePipe,
    ButtonComponent,
    DialogComponent,
    InputComponent,
    NoteComponent,
  ],
  templateUrl: './image-exception-dialog.component.html',
  styleUrl: './image-exception-dialog.component.scss',
})
export class ImageExceptionDialogComponent {
  private readonly api = inject(EventsApi);
  private readonly toast = inject(ToastService);
  private readonly i18n = inject(I18nService);

  readonly event = input.required<EventDto>();

  readonly granted = output<EventDto>();
  readonly closed = output<void>();

  protected readonly reason = signal('');
  protected readonly attempted = signal(false);
  protected readonly busy = signal(false);
  protected readonly tooShort = computed(() => this.reason().trim().length < MIN_REASON);

  protected submit(): void {
    this.attempted.set(true);
    if (this.tooShort() || this.busy()) return;
    this.busy.set(true);
    this.api
      .action(
        this.event().id,
        'image-exception',
        { reason: this.reason().trim() },
        this.event().rev,
      )
      .subscribe({
        next: (updated) => {
          this.busy.set(false);
          this.toast.success(this.i18n.translate('exception.done'));
          this.granted.emit(updated);
        },
        error: (err: unknown) => {
          this.busy.set(false);
          const problem = problemOf(err);
          const own =
            problem.status === 403
              ? 'exception.forbidden'
              : problem.status === 409
                ? 'exception.locked'
                : null;
          this.toast.error(own ? this.i18n.translate(own) : problemMessage(this.i18n, problem));
        },
      });
  }
}
