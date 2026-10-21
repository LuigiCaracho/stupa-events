/**
 * "Als Format speichern" (M5 contract 4.5): turns the dossier into a format with slug and title; the defaults (category,
 * place, duration, checklist profile) and a howto copy come from the dossier on the server. The slug follows the title
 * until it is edited by hand. On success the page reloads the dossier, which now carries the format.
 */
import { ChangeDetectionStrategy, Component, effect, inject, input, output, signal, untracked } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { problemOf } from '@core/api/problem';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { ButtonComponent, DialogComponent, InputComponent, ToastService } from '@stupa-makers/ui-kit';
import { FormatsApi } from '../../formats/api/formats-api.service';
import { SLUG_PATTERN, slugify } from '../../formats/slug';
import type { FormatOut } from '../../formats/model/format.models';
import { problemMessage } from '../api/problem-message';

@Component({
  selector: 'app-format-save-dialog',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, TranslatePipe, ButtonComponent, DialogComponent, InputComponent],
  templateUrl: './format-save-dialog.component.html',
  styleUrl: './format-save-dialog.component.scss',
})
export class FormatSaveDialogComponent {
  private readonly formats = inject(FormatsApi);
  private readonly toast = inject(ToastService);
  private readonly i18n = inject(I18nService);

  readonly eventId = input.required<string>();
  readonly suggestedTitle = input('');
  readonly saved = output<FormatOut>();
  readonly closed = output<void>();

  protected readonly busy = signal(false);
  protected readonly attempted = signal(false);
  protected readonly serverError = signal('');
  private slugTouched = false;

  protected readonly form = inject(FormBuilder).nonNullable.group({
    title: ['', [Validators.required, Validators.maxLength(120)]],
    slug: ['', [Validators.required, Validators.pattern(SLUG_PATTERN)]],
  });

  constructor() {
    effect(() => {
      const title = this.suggestedTitle();
      untracked(() => this.form.controls.title.setValue(title));
    });
    this.form.controls.title.valueChanges.subscribe((title) => {
      if (!this.slugTouched) this.form.controls.slug.setValue(slugify(title), { emitEvent: false });
    });
    this.form.controls.slug.valueChanges.subscribe(() => {
      this.slugTouched = true;
      this.serverError.set('');
    });
  }

  protected invalid(name: 'title' | 'slug'): boolean {
    return this.attempted() && this.form.controls[name].invalid;
  }

  protected submit(): void {
    this.attempted.set(true);
    if (this.form.invalid || this.busy()) return;
    const { title, slug } = this.form.getRawValue();
    this.busy.set(true);
    this.formats.saveAsFormat(this.eventId(), { slug, title: title.trim() }).subscribe({
      next: (format) => {
        this.busy.set(false);
        this.toast.success(this.i18n.translate('formatSave.saved'));
        this.saved.emit(format);
      },
      error: (err: unknown) => {
        this.busy.set(false);
        const problem = problemOf(err);
        if (problem.code === 'slug_taken') this.serverError.set(this.i18n.translate('formatSave.slugTaken'));
        else this.toast.error(problemMessage(this.i18n, problem));
      },
    });
  }
}
