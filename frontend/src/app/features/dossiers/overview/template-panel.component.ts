/**
 * "Aus der Vorlage" on the dossier overview (M5 contract 4.2): a dossier cloned from an earlier edition links to it and
 * lists what that edition shared (documents and files), since files are never copied. The source is read over the archive
 * path, so it works for an edition of another organization too. No panel, no request without `derivedFromId`.
 */
import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';
import { rxResource } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { catchError, of } from 'rxjs';
import { ArchiveApi } from '../../archive/api/archive-api.service';
import type { ArchiveEventOut } from '../../archive/model/archive.models';
import { LibraryApi } from '../../library/api/library-api.service';
import type { EventDto } from '../api/event.models';
import { resourceValue } from '@core/api/resource-value';

@Component({
  selector: 'app-template-panel',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink, TranslatePipe],
  templateUrl: './template-panel.component.html',
  styleUrl: './template-panel.component.scss',
})
export class TemplatePanelComponent {
  private readonly archive = inject(ArchiveApi);
  private readonly library = inject(LibraryApi);

  readonly event = input.required<EventDto>();

  protected readonly source = rxResource({
    params: () => this.event().derivedFromId ?? undefined,
    stream: ({ params }) => this.archive.event(params).pipe(catchError(() => of(null))),
  });
  protected readonly value = computed(() => resourceValue<ArchiveEventOut | null>(this.source, null));
  /** Read only while the panel shows a source. */
  protected readonly link = computed(() => {
    const s = this.value() as ArchiveEventOut;
    return s.own ? ['/dossiers', s.id] : ['/archiv', s.id];
  });

  protected download(id: string): string {
    return this.library.downloadUrl(id);
  }
}
