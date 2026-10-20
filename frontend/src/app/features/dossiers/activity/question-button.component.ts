/**
 * "Rückfrage" button with an inline question box (contract 6.6). It posts a comment with the given anchor and tells the
 * page; the page decides how the "Rückfrage offen" mark and the counters refresh. The box opens below the button, so it
 * works on a phone without a popover layer.
 */
import { ChangeDetectionStrategy, Component, inject, input, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { problemOf } from '@core/api/problem';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { TextareaComponent } from '@shared/ui/textarea/textarea.component';
import { ButtonComponent, ToastService } from '@stupa-makers/ui-kit';
import { CommentsApi } from '../api/comments-api.service';
import { problemMessage } from '../api/problem-message';
import type { CommentAnchor } from '../model/comment.models';

let nextId = 0;

@Component({
  selector: 'app-question-button',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [FormsModule, TranslatePipe, ButtonComponent, TextareaComponent],
  templateUrl: './question-button.component.html',
  styleUrl: './question-button.component.scss',
})
export class QuestionButtonComponent {
  private readonly api = inject(CommentsApi);
  private readonly toast = inject(ToastService);
  private readonly i18n = inject(I18nService);

  readonly eventId = input.required<string>();
  readonly anchor = input<CommentAnchor | null>(null);
  readonly what = input('');
  readonly asked = output<void>();

  protected readonly id = `question-${nextId++}`;
  protected readonly open = signal(false);
  protected readonly busy = signal(false);
  protected text = '';

  protected toggle(): void {
    this.text = '';
    this.open.update((o) => !o);
  }

  protected send(): void {
    const bodyMd = this.text.trim();
    if (!bodyMd || this.busy()) return;
    this.busy.set(true);
    this.api
      .add(this.eventId(), {
        bodyMd,
        ...(this.anchor() && { anchor: this.anchor() as CommentAnchor }),
      })
      .subscribe({
        next: () => {
          this.busy.set(false);
          this.open.set(false);
          this.toast.success(this.i18n.translate('question.sent'));
          this.asked.emit();
        },
        error: (err: unknown) => {
          this.busy.set(false);
          this.toast.error(problemMessage(this.i18n, problemOf(err)));
        },
      });
  }
}
