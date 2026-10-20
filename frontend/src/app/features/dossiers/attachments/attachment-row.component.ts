/**
 * One attachment in the tab (I08): preview, name, kind, size, scan status as text, visibility, the mark "Rückfrage
 * offen", the question button and the menu (replace, hide, download, visibility). The block only emits; the tab sends
 * the requests. A file that is not scanned clean has no download link, only its status.
 */
import { ChangeDetectionStrategy, Component, computed, inject, input, output } from '@angular/core';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { formatMegabytes } from '@shared/format.util';
import { ImageThumbComponent } from '@shared/ui/image-thumb/image-thumb.component';
import {
  RowMenuComponent,
  type RowMenuItem,
  type RowMenuSection,
} from '@shared/ui/row-menu/row-menu.component';
import { StatusTextComponent } from '@shared/ui/status-text/status-text.component';
import type { StatusKind } from '@shared/status-kind.util';
import { QuestionButtonComponent } from '../activity/question-button.component';
import type { AttachmentOut } from '../model/attachment.models';
import { visibilityOptions } from './attachment-kinds';

export type AttachmentCommand =
  { name: 'replace' | 'retire' } | { name: 'visibility'; value: 'team' | 'org' | 'shared' };

const SCAN: Record<
  string,
  {
    key:
      | 'attachment.scan.pending'
      | 'attachment.scan.clean'
      | 'attachment.scan.infected'
      | 'attachment.scan.error';
    kind: StatusKind;
  }
> = {
  pending: { key: 'attachment.scan.pending', kind: 'warn' },
  clean: { key: 'attachment.scan.clean', kind: 'accent' },
  infected: { key: 'attachment.scan.infected', kind: 'error' },
  error: { key: 'attachment.scan.error', kind: 'error' },
};

@Component({
  selector: 'app-attachment-row',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    TranslatePipe,
    ImageThumbComponent,
    QuestionButtonComponent,
    RowMenuComponent,
    StatusTextComponent,
  ],
  templateUrl: './attachment-row.component.html',
  styleUrl: './attachment-row.component.scss',
})
export class AttachmentRowComponent {
  private readonly i18n = inject(I18nService);

  readonly attachment = input.required<AttachmentOut>();
  readonly eventId = input.required<string>();
  readonly canEdit = input(false);
  readonly openQuestion = input(false);
  readonly downloadHref = input.required<string>();
  readonly previewHref = input.required<string>();

  readonly command = output<AttachmentCommand>();
  readonly asked = output<void>();
  readonly showQuestions = output<void>();

  protected readonly kindLabel = computed(() =>
    this.i18n.translate(`attachment.kind.${this.attachment().kind}`),
  );
  protected readonly visibilityLabel = computed(() =>
    this.i18n.translate(`attachment.visibility.${this.attachment().visibility}`),
  );
  protected readonly scan = computed(() => SCAN[this.attachment().scanStatus] ?? SCAN['error']);
  protected readonly size = computed(() => formatMegabytes(this.i18n, this.attachment().sizeBytes));
  protected readonly downloadable = computed(() => this.attachment().scanStatus === 'clean');

  protected readonly sections = computed<RowMenuSection[]>(() => {
    const a = this.attachment();
    const t = (k: Parameters<I18nService['translate']>[0]) => this.i18n.translate(k);
    return [
      {
        items: [
          { id: 'replace', label: t('attachment.replace'), icon: 'upload' },
          { id: 'retire', label: t('attachment.retire'), icon: 'x', danger: true },
        ],
      },
      {
        label: t('attachment.visibility'),
        items: visibilityOptions(a.kind).map((v) => ({
          id: `visibility:${v}`,
          label: t(`attachment.visibility.${v}`),
          checked: a.visibility === v,
        })),
      },
    ];
  });

  protected pick(item: RowMenuItem): void {
    if (item.id.startsWith('visibility:')) {
      this.command.emit({
        name: 'visibility',
        value: item.id.slice(11) as 'team' | 'org' | 'shared',
      });
    } else {
      this.command.emit({ name: item.id as 'replace' | 'retire' });
    }
  }
}
