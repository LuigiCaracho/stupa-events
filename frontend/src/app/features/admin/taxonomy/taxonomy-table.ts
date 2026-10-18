/**
 * Base of the three inline-editable taxonomy tables (I23). A click on a row (or "Hinzufügen")
 * turns it into a form row; saving writes through the admin API and reloads the list. Server
 * field errors land on the inputs, everything else becomes a toast. Subclasses supply the
 * columns, the form and the wire mapping.
 */
import { computed, inject, signal } from '@angular/core';
import { rxResource } from '@angular/core/rxjs-interop';
import type { FormGroup } from '@angular/forms';
import { problemOf } from '@core/api/problem';
import { I18nService } from '@core/i18n/i18n.service';
import { ToastService } from '@stupa-makers/ui-kit';
import type { Observable } from 'rxjs';
import { adminErrors } from '../admin-errors';
import { labelKey } from '../admin-labels';

export const SLUG_PATTERN = /^[a-z0-9][a-z0-9-]{0,59}$/;
export const NEW_ROW = 'new';

export abstract class TaxonomyTable<Row extends { id: string }, Value extends object> {
  protected readonly i18n = inject(I18nService);
  private readonly toast = inject(ToastService);

  protected abstract readonly form: FormGroup;
  protected abstract fetch(): Observable<Row[]>;
  protected abstract blank(): Value;
  protected abstract toValue(row: Row): Value;
  protected abstract write(id: string | null, value: Value): Observable<Row>;

  protected readonly list = rxResource({ stream: () => this.fetch() });
  protected readonly editingId = signal<string | null>(null);
  protected readonly saving = signal(false);
  protected readonly errors = signal<Record<string, string>>({});
  protected readonly isNew = computed(() => this.editingId() === NEW_ROW);
  protected readonly loaded = computed<Row[]>(() =>
    this.list.hasValue() ? this.list.value() : [],
  );

  protected readonly labelKey = labelKey;
  protected readonly rowKey = (row: unknown): string => (row as { id: string }).id;

  protected editing(row: { id: string }): boolean {
    return this.editingId() === row.id;
  }

  protected err(field: string): string {
    return this.errors()[field] ?? '';
  }

  protected startNew(): void {
    if (this.editingId() !== null) return;
    this.form.reset(this.blank());
    this.errors.set({});
    this.editingId.set(NEW_ROW);
  }

  protected startEdit(row: Row): void {
    if (this.editingId() !== null) return;
    this.form.reset(this.toValue(row));
    this.errors.set({});
    this.editingId.set(row.id);
  }

  protected cancel(): void {
    this.editingId.set(null);
    this.errors.set({});
  }

  protected validate(value: Value): Record<string, string> {
    const fields = value as Record<string, unknown>;
    const errors: Record<string, string> = {};
    if (!String(fields['name'] ?? '').trim())
      errors['name'] = this.i18n.translate('admin.err.nameRequired');
    if (this.isNew() && !SLUG_PATTERN.test(String(fields['slug'] ?? ''))) {
      errors['slug'] = this.i18n.translate('admin.err.slugInvalid');
    }
    return errors;
  }

  protected submit(): void {
    const value = this.form.getRawValue() as Value;
    const local = this.validate(value);
    this.errors.set(local);
    if (Object.keys(local).length > 0 || this.saving()) return;
    const id = this.editingId();
    this.saving.set(true);
    this.write(id === NEW_ROW ? null : id, value).subscribe({
      next: () => {
        this.saving.set(false);
        this.editingId.set(null);
        this.toast.success(this.i18n.translate('admin.saved'));
        this.list.reload();
      },
      error: (err: unknown) => {
        this.saving.set(false);
        const { fields, message } = adminErrors(this.i18n, problemOf(err));
        this.errors.set(fields);
        if (message) this.toast.error(message);
      },
    });
  }
}
