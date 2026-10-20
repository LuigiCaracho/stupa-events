/**
 * Upload form of the attachment tab (I08): drop zone, kind, visibility and, for an image, the rights block (alt text,
 * credit, rights basis, recognisable people with their consent note, date in the image). It validates and emits
 * `submitted`; the page sends the request. The same block serves "Ersetzen" with the kind fixed.
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
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { FileDropZoneComponent } from '@shared/ui/file-drop-zone/file-drop-zone.component';
import { NoteComponent } from '@shared/ui/note/note.component';
import { SelectFieldComponent, type SelectFieldOption } from '@shared/ui/select/select.component';
import { ButtonComponent, CheckboxComponent, InputComponent } from '@stupa-makers/ui-kit';
import type { RightsBasis } from '../api/event.models';
import type { AttachmentKind, AttachmentUpload } from '../model/attachment.models';
import { UPLOAD_KINDS, isImageFile, visibilityOptions } from './attachment-kinds';

const RIGHTS: readonly RightsBasis[] = [
  'own_work',
  'permission',
  'license',
  'partner_agreement',
  'unknown',
];
const ACCEPT = '.png,.jpg,.jpeg,.webp,.pdf,.docx,.xlsx,.pptx,.odt,.md,.txt,.csv';

@Component({
  selector: 'app-attachment-upload',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    ReactiveFormsModule,
    TranslatePipe,
    ButtonComponent,
    CheckboxComponent,
    FileDropZoneComponent,
    InputComponent,
    NoteComponent,
    SelectFieldComponent,
  ],
  templateUrl: './attachment-upload.component.html',
  styleUrl: './attachment-upload.component.scss',
})
export class AttachmentUploadComponent {
  private readonly i18n = inject(I18nService);

  /** A fixed kind (replace); without it the person picks one. */
  readonly fixedKind = input<AttachmentKind | null>(null);
  readonly busy = input(false);

  readonly submitted = output<AttachmentUpload>();
  readonly cancelled = output<void>();

  protected readonly accept = ACCEPT;
  protected readonly file = signal<File | null>(null);
  protected readonly rejected = signal(false);
  protected readonly attempted = signal(false);

  protected readonly form = inject(FormBuilder).nonNullable.group({
    kind: ['other' as string, [Validators.required]],
    visibility: ['org' as string],
    altText: [''],
    credit: [''],
    rightsBasis: [''],
    personsDepicted: [false],
    consentNote: [''],
    containsDate: [false],
    datedFor: [''],
  });

  protected readonly kind = computed<AttachmentKind>(
    () => this.fixedKind() ?? (this.form.controls.kind.value as AttachmentKind),
  );
  protected readonly image = computed(() => {
    const f = this.file();
    return !!f && isImageFile(f);
  });

  protected readonly kinds = computed<SelectFieldOption[]>(() =>
    UPLOAD_KINDS.map((k) => ({ value: k, label: this.i18n.translate(`attachment.kind.${k}`) })),
  );
  protected readonly visibilities = computed<SelectFieldOption[]>(() =>
    visibilityOptions(this.kind()).map((v) => ({
      value: v,
      label: this.i18n.translate(`attachment.visibility.${v}`),
    })),
  );
  protected readonly rights = computed<SelectFieldOption[]>(() =>
    RIGHTS.map((v) => ({ value: v, label: this.i18n.translate(`poster.rights.${v}`) })),
  );

  protected pick(files: File[]): void {
    this.file.set(files[0] ?? null);
    this.rejected.set(false);
  }

  protected missing(name: 'altText' | 'credit' | 'rightsBasis'): boolean {
    return this.attempted() && this.image() && this.form.controls[name].value.trim() === '';
  }

  protected consentMissing(): boolean {
    const { personsDepicted, consentNote } = this.form.getRawValue();
    return this.image() && personsDepicted && consentNote.trim() === '';
  }

  protected submit(): void {
    this.attempted.set(true);
    const file = this.file();
    const v = this.form.getRawValue();
    const invalid =
      this.image() &&
      (['altText', 'credit', 'rightsBasis'] as const).some((n) => v[n].trim() === '');
    if (!file || invalid || this.consentMissing()) return;
    const visibility = visibilityOptions(this.kind()).includes(v.visibility as never)
      ? (v.visibility as AttachmentUpload['visibility'])
      : undefined;
    this.submitted.emit({
      file,
      kind: this.kind(),
      visibility,
      ...(this.image() && {
        altText: v.altText.trim(),
        credit: v.credit.trim(),
        rightsBasis: v.rightsBasis as RightsBasis,
        personsDepicted: v.personsDepicted,
        consentNote: v.personsDepicted ? v.consentNote.trim() : undefined,
        containsDate: v.containsDate,
        datedFor: v.containsDate && v.datedFor ? Number(v.datedFor) : undefined,
      }),
    });
  }
}
