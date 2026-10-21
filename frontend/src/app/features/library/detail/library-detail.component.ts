/**
 * Detail of a library item (I19): a document is shown rendered (title, source, review state) with the button "In
 * Dossier übernehmen"; a file is a card with name, size and the download (and a preview for images). Reading goes over
 * the archive path of the server, so a deep link works without the list. The library edits nothing.
 */
import { ChangeDetectionStrategy, Component, computed, inject, input, signal } from '@angular/core';
import { rxResource } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { problemOf } from '@core/api/problem';
import { I18nService } from '@core/i18n/i18n.service';
import { LocalizedDatePipe } from '@core/i18n/localized-date.pipe';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { formatMegabytes } from '@shared/format.util';
import { MarkdownViewComponent } from '@shared/markdown/markdown-view.component';
import { ImageThumbComponent } from '@shared/ui/image-thumb/image-thumb.component';
import { NoteComponent } from '@shared/ui/note/note.component';
import { SkeletonComponent } from '@shared/ui/skeleton/skeleton.component';
import { StatusTextComponent } from '@shared/ui/status-text/status-text.component';
import { ButtonComponent } from '@stupa-makers/ui-kit';
import { LibraryApi } from '../api/library-api.service';
import { AdoptDialogComponent } from '../adopt/adopt-dialog.component';
import type { LibraryItem, LibraryKind } from '../model/library.models';

@Component({
  selector: 'app-library-detail',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    RouterLink,
    LocalizedDatePipe,
    TranslatePipe,
    AdoptDialogComponent,
    ButtonComponent,
    ImageThumbComponent,
    MarkdownViewComponent,
    NoteComponent,
    SkeletonComponent,
    StatusTextComponent,
  ],
  templateUrl: './library-detail.component.html',
  styleUrl: './library-detail.component.scss',
})
export class LibraryDetailComponent {
  private readonly api = inject(LibraryApi);
  private readonly i18n = inject(I18nService);

  readonly kind = input.required<LibraryKind>();
  readonly id = input.required<string>();
  /** The list row of this item, when the list holds it; a deep link has none. */
  readonly item = input<LibraryItem | null>(null);

  protected readonly adopting = signal(false);
  protected readonly doc = rxResource({
    params: () => (this.kind() === 'document' ? this.id() : undefined),
    stream: ({ params }) => this.api.document(params),
  });
  protected readonly notFound = computed(
    () => !!this.doc.error() && problemOf(this.doc.error()).status === 404,
  );
  protected readonly isImage = computed(() => (this.item()?.mime ?? '').startsWith('image/'));
  /** Read only inside the blocks that show an item. */
  protected readonly sourceLink = computed(() => {
    const s = (this.item() as LibraryItem).source;
    return s.type === 'format' ? ['/formate', s.id] : s.own ? ['/dossiers', s.id] : ['/archiv', s.id];
  });

  protected download(): string {
    return this.api.downloadUrl(this.id());
  }

  protected preview(): string {
    return this.api.previewUrl(this.id());
  }

  protected size(bytes: number): string {
    return `${formatMegabytes(this.i18n, bytes)} MB`;
  }
}
