/**
 * I07 (light): dossier head and overview (`/dossiers/:id`). State, core data with edit form,
 * "Fehlt noch" guard list of the next transition, poster upload, and the dialogs I13 and I15.
 * The server decides every action; `allowedTransitions` and the permission checks only shape the UI.
 */
import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  computed,
  inject,
  input,
  linkedSignal,
  signal,
} from '@angular/core';
import { rxResource } from '@angular/core/rxjs-interop';
import type { ProblemReason } from '@core/api/models';
import { problemOf } from '@core/api/problem';
import { AuthService } from '@core/auth/auth.service';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { FieldGroupComponent, FieldRowComponent } from '@shared/ui/field-group/field-group.component';
import { GuardListComponent } from '@shared/ui/guard-list/guard-list.component';
import { ImageThumbComponent } from '@shared/ui/image-thumb/image-thumb.component';
import { NoteComponent } from '@shared/ui/note/note.component';
import { PageHeaderComponent } from '@shared/ui/page-header/page-header.component';
import { PosterUploadComponent, type PosterSubmission } from '@shared/ui/poster-upload/poster-upload.component';
import { SkeletonComponent } from '@shared/ui/skeleton/skeleton.component';
import { StatusTextComponent } from '@shared/ui/status-text/status-text.component';
import { type EventState, eventStateStatus } from '@shared/status-kind.util';
import { ButtonComponent, ToastService } from '@stupa-makers/ui-kit';
import { of } from 'rxjs';
import { catchError } from 'rxjs/operators';
import { formatEventTime } from '../api/event-time';
import type { EventDto, EventPatch, TransitionId } from '../api/event.models';
import { EventsApi } from '../api/events-api.service';
import { problemMessage } from '../api/problem-message';
import { TRANSITION_LABEL } from '../api/transition-label';
import { ImageExceptionDialogComponent } from '../exception/image-exception-dialog.component';
import { TransitionDialogComponent } from '../transition/transition-dialog.component';
import { EventFormComponent } from './event-form.component';

const NEXT: Partial<Record<EventState, TransitionId>> = {
  idea: 'T01',
  planning: 'T02',
  in_review: 'T04',
  approved: 'T05',
};
const EDITABLE: readonly EventState[] = ['idea', 'planning'];
const POSTER_STATES: readonly EventState[] = ['idea', 'planning', 'in_review'];
const EXCEPTION_STATES: readonly EventState[] = ['idea', 'planning', 'in_review', 'approved'];

@Component({
  selector: 'app-dossier-detail',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    TranslatePipe,
    ButtonComponent,
    EventFormComponent,
    FieldGroupComponent,
    FieldRowComponent,
    GuardListComponent,
    ImageExceptionDialogComponent,
    ImageThumbComponent,
    NoteComponent,
    PageHeaderComponent,
    PosterUploadComponent,
    SkeletonComponent,
    StatusTextComponent,
    TransitionDialogComponent,
  ],
  templateUrl: './dossier-detail.component.html',
  styleUrl: './dossier-detail.component.scss',
})
export class DossierDetailComponent {
  private readonly api = inject(EventsApi);
  private readonly auth = inject(AuthService);
  private readonly toast = inject(ToastService);
  private readonly i18n = inject(I18nService);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);

  readonly id = input.required<string>();
  protected readonly label = TRANSITION_LABEL;

  protected readonly loaded = rxResource({
    params: () => this.id(),
    stream: ({ params }) => this.api.get(params),
  });
  protected readonly loadError = computed(() => {
    if (!this.loaded.error()) return '';
    const problem = problemOf(this.loaded.error());
    return problem.status === 403 || problem.status === 404
      ? this.i18n.translate('detail.loadFailed')
      : problemMessage(this.i18n, problem);
  });
  protected reload(): void {
    this.loaded.reload();
  }

  protected readonly event = linkedSignal<EventDto | null>(() => (this.loaded.hasValue() ? this.loaded.value() : null));

  protected readonly categories = rxResource({
    stream: () => this.api.categories().pipe(catchError(() => of([]))),
  });

  protected readonly editing = signal(false);
  protected readonly posterOpen = signal(false);
  protected readonly transitionOpen = signal<TransitionId | null>(null);
  protected readonly exceptionOpen = signal(false);
  protected readonly busy = signal(false);

  protected readonly next = computed<TransitionId | null>(() => {
    const e = this.event();
    const t = e ? (NEXT[e.state] ?? null) : null;
    return e && t && e.allowedTransitions.includes(t) ? t : null;
  });

  protected readonly guards = rxResource({
    params: () => {
      const e = this.event();
      const t = this.next();
      return e && t ? { id: e.id, transition: t, rev: e.rev } : undefined;
    },
    stream: ({ params }) => this.api.guards(params.id, params.transition),
  });

  protected readonly canEdit = computed(() => EDITABLE.includes(this.event()?.state ?? 'live'));
  protected readonly canPoster = computed(() => POSTER_STATES.includes(this.event()?.state ?? 'live'));
  protected readonly canException = computed(() => {
    const e = this.event();
    return !!e && !e.imageException && EXCEPTION_STATES.includes(e.state) && this.auth.can('event.image_exception');
  });
  protected readonly showUpload = computed(() => this.canPoster() && (this.posterOpen() || !this.event()?.poster));

  protected status(e: EventDto) {
    return eventStateStatus(e.state);
  }

  protected when(e: EventDto): string {
    return `${formatEventTime(e.startsAt, e.tzid)} – ${formatEventTime(e.endsAt, e.tzid)}`;
  }

  protected posterSrc(e: EventDto): string {
    return this.api.posterUrl(e.id, 'thumb400');
  }

  protected fix(reason: ProblemReason): void {
    this.transitionOpen.set(null);
    if (reason.fixAction === 'upload_poster') {
      this.posterOpen.set(true);
      setTimeout(() => this.host.nativeElement.querySelector('#poster-heading')?.scrollIntoView?.());
    } else if (reason.fixAction) {
      this.editing.set(true);
    }
  }

  protected applied(updated: EventDto): void {
    this.event.set(updated);
    this.transitionOpen.set(null);
    this.exceptionOpen.set(false);
  }

  protected save(patch: EventPatch): void {
    const e = this.event();
    if (!e || this.busy()) return;
    this.busy.set(true);
    this.api.patch(e.id, patch).subscribe({
      next: (updated) => {
        this.busy.set(false);
        this.editing.set(false);
        this.toast.success(this.i18n.translate('detail.saved'));
        this.event.set(updated);
      },
      error: (err: unknown) => this.failed(err),
    });
  }

  protected upload(sub: PosterSubmission): void {
    const e = this.event();
    if (!e || this.busy()) return;
    this.busy.set(true);
    this.api.uploadPoster(e.id, sub.file, sub).subscribe({
      next: () => {
        this.busy.set(false);
        this.posterOpen.set(false);
        this.toast.success(this.i18n.translate('detail.posterUploaded'));
        this.loaded.reload();
      },
      error: (err: unknown) => this.failed(err),
    });
  }

  protected reloadStale(): void {
    this.transitionOpen.set(null);
    this.loaded.reload();
  }

  private failed(err: unknown): void {
    this.busy.set(false);
    const problem = problemOf(err);
    this.toast.error(problemMessage(this.i18n, problem));
    if (problem.status === 409) this.loaded.reload();
  }
}
