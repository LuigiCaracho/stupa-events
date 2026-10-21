/**
 * One hit of the archive search (I20): title with the highlighted words, subtitle, a snippet per matching field, the
 * state as text, "Anleitung geprüft am …" or the warning "Anleitung ungeprüft", and the actions "Öffnen" and, for a
 * dossier that can be a template, "Neu aus Vorlage". Highlights come as segments and are drawn as `<mark>` elements.
 */
import { ChangeDetectionStrategy, Component, computed, input, output } from '@angular/core';
import { LocalizedDatePipe } from '@core/i18n/localized-date.pipe';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import type { TranslationKey } from '@core/i18n/translations';
import { eventStateStatus } from '@shared/status-kind.util';
import { HighlightedComponent, type TextSegment } from '@shared/ui/highlighted/highlighted.component';
import { highlightTerms } from '@shared/ui/highlighted/highlight-terms';
import { StatusTextComponent } from '@shared/ui/status-text/status-text.component';
import { ButtonComponent } from '@stupa-makers/ui-kit';
import type { HitHighlight, SearchHit } from '../model/archive.models';

const FIELD_LABELS: Record<string, TranslationKey> = {
  title: 'search.field.title',
  summary: 'search.field.summary',
  description: 'search.field.description',
  body: 'search.field.body',
  venue: 'search.field.venue',
};

@Component({
  selector: 'app-search-hit',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    LocalizedDatePipe,
    TranslatePipe,
    ButtonComponent,
    HighlightedComponent,
    StatusTextComponent,
  ],
  templateUrl: './search-hit.component.html',
  styleUrl: './search-hit.component.scss',
})
export class SearchHitComponent {
  readonly hit = input.required<SearchHit>();
  readonly query = input('');

  readonly open = output<SearchHit>();
  readonly useTemplate = output<SearchHit>();

  protected readonly titleSegments = computed<readonly TextSegment[]>(() => {
    const h = this.hit();
    const own = h.highlights.find((x) => x.field === 'title');
    return own && own.segments.length > 0 ? own.segments : highlightTerms(h.title, this.query());
  });
  protected readonly snippets = computed<HitHighlight[]>(() =>
    this.hit().highlights.filter((x) => x.field !== 'title' && x.segments.some((s) => s.hit)),
  );
  protected readonly state = computed(() => {
    const s = this.hit().state;
    return s ? eventStateStatus(s) : null;
  });
  /** Clonable are archived dossiers, and live or follow-up ones of the own organization (M5 contract 4.2). */
  protected readonly canTemplate = computed(() => {
    const h = this.hit();
    const own = !h.foreign && (h.state === 'live' || h.state === 'followup');
    return h.kind === 'event' && (h.state === 'archived' || own);
  });

  protected fieldLabel(field: string): TranslationKey | null {
    return FIELD_LABELS[field] ?? null;
  }
}
