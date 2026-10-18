/** Dialog "Organisation zuweisen" (editorial staff): gives a proposal without organization to one of the organizations. */
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
import { SelectFieldComponent, type SelectFieldOption } from '@shared/ui/select/select.component';
import { ButtonComponent, DialogComponent, ToastService } from '@stupa-makers/ui-kit';
import { of } from 'rxjs';
import { catchError } from 'rxjs/operators';
import type { EventDto } from '../api/event.models';
import { EventsApi } from '../api/events-api.service';
import { problemMessage } from '../api/problem-message';

@Component({
  selector: 'app-assign-org-dialog',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [TranslatePipe, ButtonComponent, DialogComponent, SelectFieldComponent],
  templateUrl: './assign-org-dialog.component.html',
  styleUrl: './assign-org-dialog.component.scss',
})
export class AssignOrgDialogComponent {
  private readonly api = inject(EventsApi);
  private readonly toast = inject(ToastService);
  private readonly i18n = inject(I18nService);

  readonly event = input.required<EventDto>();
  readonly done = output<EventDto>();
  readonly stale = output<void>();
  readonly closed = output<void>();

  protected readonly orgId = signal('');
  protected readonly attempted = signal(false);
  protected readonly busy = signal(false);

  protected readonly orgs = rxResource({
    stream: () => this.api.allOrganizations().pipe(catchError(() => of([]))),
  });
  protected readonly options = computed<SelectFieldOption[]>(() =>
    (this.orgs.hasValue() ? this.orgs.value() : []).map((o) => ({ value: o.id, label: o.name })),
  );

  protected submit(): void {
    this.attempted.set(true);
    if (!this.orgId() || this.busy()) return;
    this.busy.set(true);
    const e = this.event();
    this.api
      .action(e.id, 'assign-organization', { organizationId: this.orgId() }, e.rev)
      .subscribe({
        next: (updated) => {
          this.busy.set(false);
          this.toast.success(this.i18n.translate('assign.done'));
          this.done.emit(updated);
        },
        error: (err: unknown) => {
          this.busy.set(false);
          const problem = problemOf(err);
          this.toast.error(problemMessage(this.i18n, problem));
          if (problem.status === 409) this.stale.emit();
        },
      });
  }
}
