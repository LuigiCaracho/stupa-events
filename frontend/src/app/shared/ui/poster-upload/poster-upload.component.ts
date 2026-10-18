/**
 * Poster upload form of a dossier: file, alt text, credit and rights basis in one block. It
 * validates the required fields and emits `submitted`; the page sends the request (PLAN 4.4, 9.1).
 */
import { ChangeDetectionStrategy, Component, computed, inject, input, output, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { ButtonComponent, InputComponent } from '@stupa-makers/ui-kit';
import { FileDropZoneComponent } from '../file-drop-zone/file-drop-zone.component';
import { NoteComponent } from '../note/note.component';
import { SelectFieldComponent, type SelectFieldOption } from '../select/select.component';

export type PosterRights = 'own_work' | 'permission' | 'license' | 'partner_agreement' | 'unknown';

export interface PosterSubmission {
  file: File;
  altText: string;
  credit: string;
  rightsBasis: PosterRights;
}

const RIGHTS: readonly PosterRights[] = [
  'own_work',
  'permission',
  'license',
  'partner_agreement',
  'unknown',
];

@Component({
  selector: 'app-poster-upload',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    ReactiveFormsModule,
    TranslatePipe,
    ButtonComponent,
    InputComponent,
    FileDropZoneComponent,
    NoteComponent,
    SelectFieldComponent,
  ],
  templateUrl: './poster-upload.component.html',
  styleUrl: './poster-upload.component.scss',
})
export class PosterUploadComponent {
  private readonly i18n = inject(I18nService);

  readonly busy = input(false);

  readonly submitted = output<PosterSubmission>();

  protected readonly accept = 'image/jpeg,image/png,image/webp';
  protected readonly file = signal<File | null>(null);
  protected readonly rejected = signal(false);
  protected readonly attempted = signal(false);

  protected readonly form = inject(FormBuilder).nonNullable.group({
    altText: ['', [Validators.required, Validators.maxLength(250)]],
    credit: ['', [Validators.required, Validators.maxLength(200)]],
    rightsBasis: ['', [Validators.required]],
  });

  protected readonly rights = computed<SelectFieldOption[]>(() =>
    RIGHTS.map((value) => ({ value, label: this.i18n.translate(`poster.rights.${value}`) })),
  );

  protected pick(files: File[]): void {
    this.file.set(files[0] ?? null);
    this.rejected.set(false);
  }

  protected invalid(name: 'altText' | 'credit' | 'rightsBasis'): boolean {
    return this.attempted() && this.form.controls[name].invalid;
  }

  protected submit(): void {
    this.attempted.set(true);
    const file = this.file();
    if (!file || this.form.invalid) return;
    const { altText, credit, rightsBasis } = this.form.getRawValue();
    this.submitted.emit({ file, altText: altText.trim(), credit: credit.trim(), rightsBasis: rightsBasis as PosterRights });
  }
}
