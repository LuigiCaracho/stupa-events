/**
 * Compare two revisions of the dossier (I12): short fields through the kit's config diff, long texts through
 * `app-markdown-diff` with a line diff. Both revisions come from `GET /events/{id}/revisions/{rev}`.
 */
import { ChangeDetectionStrategy, Component, computed, inject, input, signal } from '@angular/core';
import { problemOf } from '@core/api/problem';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { fieldLabel } from '@shared/ui/guard-list/reason-text';
import { MarkdownDiffComponent } from '@shared/ui/markdown-diff/markdown-diff.component';
import { NoteComponent } from '@shared/ui/note/note.component';
import { SelectFieldComponent, type SelectFieldOption } from '@shared/ui/select/select.component';
import { SkeletonComponent } from '@shared/ui/skeleton/skeleton.component';
import { ButtonComponent, ConfigDiffComponent, type ConfigDiffData } from '@stupa-makers/ui-kit';
import { forkJoin } from 'rxjs';
import type { RevisionDetail, RevisionOut } from '../api/action.models';
import { EventsApi } from '../api/events-api.service';
import { problemMessage } from '../api/problem-message';
import type { DiffOut } from '../model/document.models';
import { lineDiff } from './line-diff';

const LONG_TEXT = 120;
const isLong = (v: unknown): v is string =>
  typeof v === 'string' && (v.includes('\n') || v.length > LONG_TEXT);

@Component({
  selector: 'app-revision-compare',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    TranslatePipe,
    ButtonComponent,
    ConfigDiffComponent,
    MarkdownDiffComponent,
    NoteComponent,
    SelectFieldComponent,
    SkeletonComponent,
  ],
  templateUrl: './revision-compare.component.html',
  styleUrl: './revision-compare.component.scss',
})
export class RevisionCompareComponent {
  private readonly api = inject(EventsApi);
  private readonly i18n = inject(I18nService);

  readonly eventId = input.required<string>();
  readonly revisions = input.required<readonly RevisionOut[]>();

  protected readonly from = signal('');
  protected readonly to = signal('');
  protected readonly short = signal<ConfigDiffData | null>(null);
  protected readonly texts = signal<{ label: string; diff: DiffOut }[]>([]);
  protected readonly error = signal('');
  protected readonly loading = signal(false);

  protected readonly options = computed<SelectFieldOption[]>(() =>
    this.revisions().map((r) => ({
      value: String(r.rev),
      label: this.i18n.translate('history.rev', { rev: r.rev }),
    })),
  );

  protected compare(): void {
    const from = Number(this.from());
    const to = Number(this.to());
    if (!from || !to) return;
    this.loading.set(true);
    this.error.set('');
    forkJoin([
      this.api.revision(this.eventId(), from),
      this.api.revision(this.eventId(), to),
    ]).subscribe({
      next: ([a, b]) => {
        this.loading.set(false);
        this.show(a, b);
      },
      error: (err: unknown) => {
        this.loading.set(false);
        this.error.set(problemMessage(this.i18n, problemOf(err)));
      },
    });
  }

  private show(a: RevisionDetail, b: RevisionDetail): void {
    const changed: ConfigDiffData['changed'] = [];
    const texts: { label: string; diff: DiffOut }[] = [];
    const keys = new Set([...Object.keys(a.snapshot), ...Object.keys(b.snapshot)]);
    for (const key of keys) {
      const before = a.snapshot[key];
      const after = b.snapshot[key];
      if (JSON.stringify(before) === JSON.stringify(after)) continue;
      const label = fieldLabel(this.i18n, key);
      if (isLong(before) || isLong(after)) {
        const diff = lineDiff(String(before ?? ''), String(after ?? ''), a.rev, b.rev);
        if (diff) texts.push({ label, diff });
      } else {
        changed.push({ key: label, old: before ?? '', new: after ?? '' });
      }
    }
    this.short.set({ added: [], removed: [], changed });
    this.texts.set(texts);
  }
}
