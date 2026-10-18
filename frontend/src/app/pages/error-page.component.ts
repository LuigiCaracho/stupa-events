/** 403 and 404 pages: one sentence, no distinction between "missing" and "not allowed" on 404. */
import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { RouterLink } from '@angular/router';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import type { TranslationKey } from '@core/i18n/translations';
import { EmptyStateComponent } from '@shared/ui/empty-state/empty-state.component';

@Component({
  selector: 'app-error-page',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [TranslatePipe, EmptyStateComponent, RouterLink],
  template: `
    <app-empty-state
      plain
      level="1"
      [heading]="heading() | t"
      [body]="body() | t"
      [code]="code()"
    />
    <a routerLink="/">{{ 'common.back' | t }}</a>
  `,
})
export class ErrorPageComponent {
  readonly heading = input.required<TranslationKey>();
  readonly body = input.required<TranslationKey>();
  readonly code = input<string | null>(null);
}
