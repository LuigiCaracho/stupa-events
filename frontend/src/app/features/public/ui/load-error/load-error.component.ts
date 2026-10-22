/** The failure note of a public page: "Die Termine konnten nicht geladen werden." with a reload button, or the 429 sentence. */
import { ChangeDetectionStrategy, Component, computed, input, output } from '@angular/core';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import type { TranslationKey } from '@core/i18n/translations';
import { NoteComponent } from '@shared/ui/note/note.component';
import { ButtonComponent } from '@stupa-makers/ui-kit';
import type { PublicErrorKind } from '../../api/public-error';

const TEXT: Record<PublicErrorKind, TranslationKey> = {
  notFound: 'public.error.failed',
  failed: 'public.error.failed',
  rateLimited: 'public.error.rateLimited',
  queryTooLong: 'public.error.queryTooLong',
  invalidQuery: 'public.error.invalidQuery',
};

@Component({
  selector: 'app-load-error',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [NoteComponent, ButtonComponent, TranslatePipe],
  template: `
    <app-note kind="error" icon="alert" role="alert">
      <span>{{ text() | t }}</span>
      @if (retryable()) {
        <app-button variant="text" size="sm" (click)="retry.emit()">{{
          'public.error.reload' | t
        }}</app-button>
      }
    </app-note>
  `,
})
export class LoadErrorComponent {
  readonly kind = input<PublicErrorKind>('failed');
  readonly retry = output<void>();
  protected readonly text = computed(() => TEXT[this.kind()]);
  protected readonly retryable = computed(
    () => this.kind() === 'failed' || this.kind() === 'rateLimited',
  );
}
