/**
 * The edit conflict (409 on a draft or a save, or a draft older than the dossier): shows base, own and current value of
 * each field and lets the person choose per contested field. "Übernehmen" sends the kept own values on top of the
 * current version; "Neu laden" throws the own changes away. Nothing is overwritten without a look at the difference.
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
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { fieldLabel } from '@shared/ui/guard-list/reason-text';
import { NoteComponent } from '@shared/ui/note/note.component';
import {
  ButtonComponent,
  ConfigDiffComponent,
  DialogComponent,
  SegmentedComponent,
} from '@stupa-makers/ui-kit';
import type { CategoryRef, EventDto, EventFields, VenueRef } from '../api/event.models';
import {
  type Choice,
  type ConflictRow,
  chosenFields,
  conflictRows,
  formatValue,
  serverDiff,
} from './conflict-model';

@Component({
  selector: 'app-conflict-dialog',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    TranslatePipe,
    ButtonComponent,
    ConfigDiffComponent,
    DialogComponent,
    NoteComponent,
    SegmentedComponent,
  ],
  templateUrl: './conflict-dialog.component.html',
  styleUrl: './conflict-dialog.component.scss',
})
export class ConflictDialogComponent {
  private readonly i18n = inject(I18nService);

  readonly current = input.required<EventDto>();
  readonly mine = input.required<EventFields>();
  readonly base = input<Record<string, unknown> | null>(null);
  readonly venues = input<readonly VenueRef[]>([]);
  readonly categories = input<readonly CategoryRef[]>([]);
  readonly busy = input(false);

  /** The own fields to keep, to send on top of the current version. */
  readonly keep = output<EventFields>();
  readonly reload = output<void>();
  readonly closed = output<void>();

  protected readonly choices = signal<Readonly<Record<string, Choice>>>({});
  protected readonly rows = computed(() => conflictRows(this.mine(), this.current(), this.base()));
  protected readonly diff = computed(() => serverDiff(this.rows()));
  protected readonly hasBase = computed(() => this.base() !== null);
  protected readonly options = computed(() => [
    { value: 'mine', label: this.i18n.translate('conflict.keepMine') },
    { value: 'theirs', label: this.i18n.translate('conflict.takeTheirs') },
  ]);

  protected label(row: ConflictRow): string {
    return fieldLabel(this.i18n, row.field);
  }

  protected show(row: ConflictRow, value: unknown): string {
    return formatValue(row.field, value, {
      tzid: this.current().tzid,
      venues: this.venues(),
      categories: this.categories(),
      empty: this.i18n.translate('conflict.empty'),
    });
  }

  protected choice(row: ConflictRow): Choice {
    return this.choices()[row.field] ?? 'theirs';
  }

  protected choose(row: ConflictRow, value: string | null): void {
    this.choices.update((c) => ({ ...c, [row.field]: (value as Choice) ?? 'theirs' }));
  }

  protected apply(): void {
    this.keep.emit(chosenFields(this.rows(), this.choices(), this.mine()));
  }
}
