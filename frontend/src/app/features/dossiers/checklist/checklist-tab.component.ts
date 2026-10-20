/**
 * I10 Checkliste: the points of the dossier grouped by phase, "Vorlage anwenden", a form for an own point and the
 * per-point commands (tick, assign, waive with reason, delete). The server rules (reason length, member check,
 * template points) answer as Problem+JSON and surface as toasts. Counters refresh through `changed`.
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
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { problemOf } from '@core/api/problem';
import { AuthService } from '@core/auth/auth.service';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { EmptyStateComponent } from '@shared/ui/empty-state/empty-state.component';
import { NoteComponent } from '@shared/ui/note/note.component';
import { SelectFieldComponent, type SelectFieldOption } from '@shared/ui/select/select.component';
import { SkeletonComponent } from '@shared/ui/skeleton/skeleton.component';
import {
  ButtonComponent,
  CheckboxComponent,
  InputComponent,
  ToastService,
} from '@stupa-makers/ui-kit';
import type { Observable } from 'rxjs';
import { ChecklistApi } from '../api/checklist-api.service';
import type { EventDto } from '../api/event.models';
import { problemMessage } from '../api/problem-message';
import {
  CHECKLIST_PHASES,
  type ChecklistItemOut,
  type ChecklistPhase,
} from '../model/checklist.models';
import { ChecklistItemComponent, type ChecklistCommand } from './checklist-item.component';

@Component({
  selector: 'app-checklist-tab',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    ReactiveFormsModule,
    TranslatePipe,
    ButtonComponent,
    CheckboxComponent,
    ChecklistItemComponent,
    EmptyStateComponent,
    InputComponent,
    NoteComponent,
    SelectFieldComponent,
    SkeletonComponent,
  ],
  templateUrl: './checklist-tab.component.html',
  styleUrl: './checklist-tab.component.scss',
})
export class ChecklistTabComponent {
  private readonly api = inject(ChecklistApi);
  private readonly auth = inject(AuthService);
  private readonly toast = inject(ToastService);
  private readonly i18n = inject(I18nService);

  readonly event = input.required<EventDto>();
  readonly canEdit = input(false);

  readonly changed = output<void>();

  protected readonly list = rxResource({
    params: () => this.event().id,
    stream: ({ params }) => this.api.get(params),
  });
  protected readonly busy = signal(false);
  protected readonly adding = signal(false);
  protected readonly attempted = signal(false);
  protected readonly form = inject(FormBuilder).nonNullable.group({
    text: ['', [Validators.required, Validators.maxLength(240)]],
    phase: ['planning' as string],
    required: [false],
  });

  protected readonly phaseOptions = computed<SelectFieldOption[]>(() =>
    CHECKLIST_PHASES.map((p) => ({ value: p, label: this.i18n.translate(`checklist.phase.${p}`) })),
  );

  protected readonly groups = computed(() => {
    const items = this.list.hasValue() ? this.list.value().items : [];
    return CHECKLIST_PHASES.map((phase) => ({
      phase,
      items: items.filter((i) => i.phase === phase).sort((a, b) => a.position - b.position),
    })).filter((g) => g.items.length > 0);
  });

  protected readonly assignees = computed<SelectFieldOption[]>(() => {
    const me = this.auth.userId();
    const known = new Map<string, string>();
    if (me) known.set(me, this.auth.displayName() || this.i18n.translate('checklist.me'));
    (this.list.hasValue() ? this.list.value().items : []).forEach((i) => {
      if (i.assigneeSub) known.set(i.assigneeSub, i.assigneeName ?? i.assigneeSub);
    });
    return [...known].map(([value, label]) => ({ value, label }));
  });

  protected phaseLabel(phase: ChecklistPhase): string {
    return this.i18n.translate(`checklist.phase.${phase}`);
  }

  protected canTick(item: ChecklistItemOut): boolean {
    return this.canEdit() || item.assigneeSub === this.auth.userId();
  }

  protected apply(): void {
    this.run(this.api.applyTemplate(this.event().id), (out) => {
      const added = (out as { added?: number }).added ?? 0;
      this.toast.success(this.i18n.translate('checklist.applied', { count: added }));
    });
  }

  protected add(): void {
    this.attempted.set(true);
    if (this.form.invalid) return;
    const v = this.form.getRawValue();
    this.run(
      this.api.add(this.event().id, {
        text: v.text.trim(),
        phase: v.phase as ChecklistPhase,
        required: v.required,
      }),
      () => {
        this.form.reset({ text: '', phase: v.phase, required: false });
        this.attempted.set(false);
        this.adding.set(false);
      },
    );
  }

  protected command(item: ChecklistItemOut, c: ChecklistCommand): void {
    switch (c.name) {
      case 'done':
        return this.run(this.api.done(item.id, c.done));
      case 'assign':
        return this.run(this.api.patch(item.id, { assigneeSub: c.sub }));
      case 'waive':
        return this.run(this.api.patch(item.id, { waivedReason: c.reason }));
      case 'delete':
        return this.run(this.api.remove(item.id));
    }
  }

  private run(call: Observable<unknown>, done?: (out: unknown) => void): void {
    this.busy.set(true);
    call.subscribe({
      next: (out) => {
        this.busy.set(false);
        done?.(out);
        this.list.reload();
        this.changed.emit();
      },
      error: (err: unknown) => {
        this.busy.set(false);
        this.toast.error(problemMessage(this.i18n, problemOf(err)));
      },
    });
  }
}
