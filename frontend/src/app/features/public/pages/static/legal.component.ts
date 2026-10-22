/** Impressum and Datenschutz (P14): placeholders until the university and the data protection officer have agreed the text. */
import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { usePageTitle } from '../../ui/page-title';

@Component({
  selector: 'app-legal-page',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [TranslatePipe],
  template: `
    <h1 class="legal__title">
      {{ (kind() === 'imprint' ? 'public.legal.imprint' : 'public.legal.privacy') | t }}
    </h1>
    <p class="legal__body">{{ 'public.legal.placeholder' | t }}</p>
  `,
  styleUrl: './static.scss',
})
export class LegalPageComponent {
  private readonly i18n = inject(I18nService);
  readonly kind = input.required<'imprint' | 'privacy'>();

  constructor() {
    const name = computed(() =>
      this.i18n.translate(
        this.kind() === 'imprint' ? 'public.legal.imprint' : 'public.legal.privacy',
      ),
    );
    usePageTitle(name);
  }
}
