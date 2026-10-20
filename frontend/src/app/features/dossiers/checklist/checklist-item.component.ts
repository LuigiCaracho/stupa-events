/**
 * One checklist point (I10): checkbox, text, the word "Pflicht" for required points, the assignee, the due chip
 * (relative and absolute, "überfällig" as text and in the error colour) and the menu. Waiving asks for a reason in
 * the row. The block only emits; the tab sends the requests.
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
import { FormsModule } from '@angular/forms';
import { I18nService } from '@core/i18n/i18n.service';
import { LocalizedDatePipe } from '@core/i18n/localized-date.pipe';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import {
  RowMenuComponent,
  type RowMenuItem,
  type RowMenuSection,
} from '@shared/ui/row-menu/row-menu.component';
import { SelectFieldComponent, type SelectFieldOption } from '@shared/ui/select/select.component';
import { StatusTextComponent } from '@shared/ui/status-text/status-text.component';
import { TextareaComponent } from '@shared/ui/textarea/textarea.component';
import { ButtonComponent, CheckboxComponent } from '@stupa-makers/ui-kit';
import type { ChecklistItemOut } from '../model/checklist.models';
import { relativeDue } from './due-label';

export type ChecklistCommand =
  | { name: 'done'; done: boolean }
  | { name: 'assign'; sub: string | null }
  | { name: 'waive'; reason: string }
  | { name: 'delete' };

@Component({
  selector: 'app-checklist-item',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    FormsModule,
    LocalizedDatePipe,
    TranslatePipe,
    ButtonComponent,
    CheckboxComponent,
    RowMenuComponent,
    SelectFieldComponent,
    StatusTextComponent,
    TextareaComponent,
  ],
  templateUrl: './checklist-item.component.html',
  styleUrl: './checklist-item.component.scss',
})
export class ChecklistItemComponent {
  private readonly i18n = inject(I18nService);

  readonly item = input.required<ChecklistItemOut>();
  readonly canEdit = input(false);
  readonly canTick = input(false);
  readonly assignees = input<readonly SelectFieldOption[]>([]);

  readonly command = output<ChecklistCommand>();

  protected readonly waiving = signal(false);
  protected readonly assigning = signal(false);
  protected reason = '';

  protected readonly relative = computed(() => relativeDue(this.i18n, this.item().dueOffsetDays));
  protected readonly state = computed(() => {
    const i = this.item();
    return i.waivedReason ? 'waived' : i.doneAt ? 'done' : 'open';
  });
  protected reasonTooShort(): boolean {
    return this.item().required && this.reason.trim().length < 10;
  }

  protected readonly sections = computed<RowMenuSection[]>(() => {
    const t = (k: Parameters<I18nService['translate']>[0]) => this.i18n.translate(k);
    const i = this.item();
    return [
      {
        items: [
          { id: 'assign', label: t('checklist.assign'), icon: 'user' },
          { id: 'waive', label: t('checklist.waive'), icon: 'minus', disabled: !!i.doneAt },
          ...(i.fromTemplate
            ? []
            : [
                {
                  id: 'delete',
                  label: t('checklist.delete'),
                  icon: 'trash' as const,
                  danger: true,
                },
              ]),
        ],
      },
    ];
  });

  protected pick(entry: RowMenuItem): void {
    if (entry.id === 'assign') this.assigning.set(true);
    else if (entry.id === 'waive') this.waiving.set(true);
    else this.command.emit({ name: 'delete' });
  }

  protected assign(sub: string): void {
    this.assigning.set(false);
    this.command.emit({ name: 'assign', sub: sub || null });
  }

  protected waive(): void {
    if (this.reasonTooShort() || !this.reason.trim()) return;
    this.command.emit({ name: 'waive', reason: this.reason.trim() });
    this.waiving.set(false);
    this.reason = '';
  }
}
