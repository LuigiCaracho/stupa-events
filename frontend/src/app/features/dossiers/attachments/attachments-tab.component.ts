/**
 * I08 Anhänge: the groups poster, social posts, documents, quote files and other, with upload, replace, hide and
 * visibility. The server filters what a person may see (contract 3.7); this section shows exactly what comes back and
 * never an empty group. The comparison quotes are the section next to it (`app-quotes-tab`). Requests go through
 * `AttachmentsApi`; every success tells the page.
 */
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  input,
  output,
  signal,
} from '@angular/core';
import { rxResource } from '@angular/core/rxjs-interop';
import { problemOf } from '@core/api/problem';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { EmptyStateComponent } from '@shared/ui/empty-state/empty-state.component';
import { NoteComponent } from '@shared/ui/note/note.component';
import { SkeletonComponent } from '@shared/ui/skeleton/skeleton.component';
import { ButtonComponent, ToastService } from '@stupa-makers/ui-kit';
import type { Observable } from 'rxjs';
import { AttachmentsApi } from '../api/attachments-api.service';
import { problemMessage } from '../api/problem-message';
import type { EventDto } from '../api/event.models';
import type { CommentThread } from '../model/comment.models';
import type { AttachmentOut, AttachmentUpload } from '../model/attachment.models';
import { GROUP_ORDER, type AttachmentGroupId, groupOf } from './attachment-kinds';
import { AttachmentRowComponent, type AttachmentCommand } from './attachment-row.component';
import { AttachmentUploadComponent } from './attachment-upload.component';

interface Group {
  id: AttachmentGroupId;
  current: AttachmentOut[];
  older: AttachmentOut[];
}

@Component({
  selector: 'app-attachments-tab',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    TranslatePipe,
    AttachmentRowComponent,
    AttachmentUploadComponent,
    ButtonComponent,
    EmptyStateComponent,
    NoteComponent,
    SkeletonComponent,
  ],
  templateUrl: './attachments-tab.component.html',
  styleUrl: './attachments-tab.component.scss',
})
export class AttachmentsTabComponent {
  private readonly api = inject(AttachmentsApi);
  private readonly toast = inject(ToastService);
  private readonly i18n = inject(I18nService);

  readonly event = input.required<EventDto>();
  readonly canEdit = input(false);
  readonly threads = input<readonly CommentThread[]>([]);

  readonly changed = output<void>();
  readonly showQuestions = output<void>();

  protected readonly list = rxResource({
    params: () => ({ id: this.event().id, rev: this.event().rev }),
    stream: ({ params }) => this.api.list(params.id, true),
  });

  protected readonly busy = signal(false);
  protected readonly uploading = signal(false);
  protected readonly replacing = signal<AttachmentOut | null>(null);

  protected readonly groups = computed<Group[]>(() => {
    const items = this.list.hasValue() ? this.list.value() : [];
    return GROUP_ORDER.map((id) => {
      const own = items.filter((a) => groupOf(a.kind) === id);
      return {
        id,
        current: own.filter((a) => !a.retiredAt),
        older: own.filter((a) => !!a.retiredAt),
      };
    }).filter((g) => g.current.length > 0 || g.older.length > 0);
  });

  protected readonly openAttachments = computed(
    () =>
      new Set(
        this.threads()
          .filter((t) => !t.resolvedAt && t.anchor && 'attachmentId' in t.anchor)
          .map((t) => (t.anchor as { attachmentId: string }).attachmentId),
      ),
  );

  protected groupLabel(id: AttachmentGroupId): string {
    return this.i18n.translate(`attachment.group.${id}`);
  }

  protected href(id: string): string {
    return this.api.downloadUrl(id);
  }

  protected preview(id: string): string {
    return this.api.previewUrl(id);
  }

  protected upload(upload: AttachmentUpload): void {
    this.run(this.api.upload(this.event().id, upload), upload.file, () =>
      this.uploading.set(false),
    );
  }

  protected replaceWith(upload: AttachmentUpload): void {
    const target = this.replacing();
    if (!target) return;
    this.run(this.api.replace(target.id, upload), upload.file, () => this.replacing.set(null));
  }

  protected command(a: AttachmentOut, c: AttachmentCommand): void {
    if (c.name === 'visibility') return this.run(this.api.patch(a.id, { visibility: c.value }));
    if (c.name === 'replace') return this.replacing.set(a);
    this.run(this.api.retire(a.id));
  }

  protected refresh(): void {
    this.list.reload();
    this.changed.emit();
  }

  private run(call: Observable<unknown>, file?: File, done?: () => void): void {
    this.busy.set(true);
    call.subscribe({
      next: () => {
        this.busy.set(false);
        done?.();
        this.refresh();
      },
      error: (err: unknown) => {
        this.busy.set(false);
        this.toast.error(this.errorText(err, file));
      },
    });
  }

  private errorText(err: unknown, file?: File): string {
    const problem = problemOf(err);
    if (problem.code === 'file_too_large' && file) {
      return this.i18n.translate('attachment.tooLarge', {
        size: (file.size / 1_048_576).toFixed(1).replace('.', ','),
        limit: Math.round((problem.limitBytes ?? 26_214_400) / 1_048_576),
      });
    }
    return problemMessage(this.i18n, problem);
  }
}
