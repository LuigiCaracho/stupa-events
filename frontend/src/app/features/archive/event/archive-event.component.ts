/**
 * Read-only view of an archived dossier (`/archiv/:id`, M5 contract 4.1): the core data that another organization may
 * see (title, texts, date, place, format, attendance), the shared documents and files, and the way to a new edition
 * ("Neu aus Vorlage"). Costs, notes, comments and the checklist are never part of the answer.
 */
import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';
import { rxResource } from '@angular/core/rxjs-interop';
import { Router, RouterLink } from '@angular/router';
import { problemOf } from '@core/api/problem';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { formatMegabytes } from '@shared/format.util';
import { MarkdownViewComponent } from '@shared/markdown/markdown-view.component';
import { eventStateStatus } from '@shared/status-kind.util';
import { NoteComponent } from '@shared/ui/note/note.component';
import { PageHeaderComponent } from '@shared/ui/page-header/page-header.component';
import { SkeletonComponent } from '@shared/ui/skeleton/skeleton.component';
import { StatusTextComponent } from '@shared/ui/status-text/status-text.component';
import { ButtonComponent } from '@stupa-makers/ui-kit';
import { formatEventTime } from '../../dossiers/api/event-time';
import { LibraryApi } from '../../library/api/library-api.service';
import { ArchiveApi } from '../api/archive-api.service';
import type { ArchiveEventOut } from '../model/archive.models';
import { resourceValue } from '@core/api/resource-value';

const TZID = 'Europe/Berlin';

@Component({
  selector: 'app-archive-event',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    RouterLink,
    TranslatePipe,
    ButtonComponent,
    MarkdownViewComponent,
    NoteComponent,
    PageHeaderComponent,
    SkeletonComponent,
    StatusTextComponent,
  ],
  templateUrl: './archive-event.component.html',
  styleUrl: './archive-event.component.scss',
})
export class ArchiveEventComponent {
  private readonly api = inject(ArchiveApi);
  private readonly library = inject(LibraryApi);
  private readonly router = inject(Router);
  private readonly i18n = inject(I18nService);

  readonly id = input.required<string>();

  protected readonly loaded = rxResource({
    params: () => this.id(),
    stream: ({ params }) => this.api.event(params),
  });
  protected readonly event = computed(() => resourceValue<ArchiveEventOut | null>(this.loaded, null));
  /** The two below are only read while the dossier is shown. */
  protected readonly state = computed(() => eventStateStatus((this.event() as ArchiveEventOut).state));
  protected readonly when = computed(() => {
    const e = this.event() as ArchiveEventOut;
    return `${formatEventTime(e.startsAt, TZID)} – ${formatEventTime(e.endsAt, TZID)}`;
  });
  protected readonly notFound = computed(
    () => !!this.loaded.error() && problemOf(this.loaded.error()).status === 404,
  );

  protected size(bytes: number): string {
    return `${formatMegabytes(this.i18n, bytes)} MB`;
  }

  protected download(id: string): string {
    return this.library.downloadUrl(id);
  }

  protected useTemplate(): void {
    void this.router.navigate(['/dossiers/neu'], { queryParams: { vorlage: this.id() } });
  }
}
