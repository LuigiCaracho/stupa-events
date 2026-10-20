/**
 * "Rückfragen zu Angaben" block of the overview (contract 6.6): one row per anchorable field (poster, title, short
 * text, description, date, place) with the mark "Rückfrage offen" when a thread on it is open and a question button.
 * The form fields themselves stay untouched; this block is the place where a reviewer asks about one of them.
 */
import { ChangeDetectionStrategy, Component, computed, input, output } from '@angular/core';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import type { TranslationKey } from '@core/i18n/translations';
import { StatusTextComponent } from '@shared/ui/status-text/status-text.component';
import type { CommentThread } from '../model/comment.models';
import { QuestionButtonComponent } from './question-button.component';

export const ANCHOR_FIELDS: readonly { field: string; label: TranslationKey }[] = [
  { field: 'hero', label: 'anchor.poster' },
  { field: 'title', label: 'field.title' },
  { field: 'summary', label: 'field.summary' },
  { field: 'descriptionMd', label: 'field.descriptionMd' },
  { field: 'startsAt', label: 'field.startsAt' },
  { field: 'venueText', label: 'field.venueText' },
];

@Component({
  selector: 'app-field-questions',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [TranslatePipe, QuestionButtonComponent, StatusTextComponent],
  templateUrl: './field-questions.component.html',
  styleUrl: './field-questions.component.scss',
})
export class FieldQuestionsComponent {
  readonly eventId = input.required<string>();
  readonly threads = input<readonly CommentThread[]>([]);
  readonly canComment = input(false);

  readonly asked = output<void>();
  readonly show = output<void>();

  protected readonly rows = computed(() => {
    const open = new Set(
      this.threads()
        .filter((t) => !t.resolvedAt && t.anchor && 'field' in t.anchor)
        .map((t) => (t.anchor as { field: string }).field),
    );
    return ANCHOR_FIELDS.map((f) => ({ ...f, open: open.has(f.field) }));
  });
}
