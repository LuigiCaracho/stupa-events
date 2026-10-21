/**
 * "Neue Ausgabe planen" for a format without an archived edition: the date and, if there is a choice, the organization;
 * the server builds a fresh dossier from the defaults of the format (`POST /formats/{slug}/new-edition`). With earlier
 * editions the format page opens the clone dialog I06 instead, which shows the preview.
 */
import { ChangeDetectionStrategy, Component, computed, inject, input, output, signal } from '@angular/core';
import { rxResource } from '@angular/core/rxjs-interop';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { problemOf } from '@core/api/problem';
import { AuthService } from '@core/auth/auth.service';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { SelectFieldComponent, type SelectFieldOption } from '@shared/ui/select/select.component';
import {
  ButtonComponent,
  DatepickerComponent,
  DialogComponent,
  TimeInputComponent,
  ToastService,
} from '@stupa-makers/ui-kit';
import { catchError, of } from 'rxjs';
import { zonedToIso } from '../../dossiers/api/event-time';
import type { OrgRef } from '../../dossiers/api/event.models';
import { EventsApi } from '../../dossiers/api/events-api.service';
import { problemMessage } from '../../dossiers/api/problem-message';
import { FormatsApi } from '../api/formats-api.service';
import type { FormatOut, NewEditionIn } from '../model/format.models';

const TZID = 'Europe/Berlin';

@Component({
  selector: 'app-new-edition-dialog',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    ReactiveFormsModule,
    TranslatePipe,
    ButtonComponent,
    DatepickerComponent,
    DialogComponent,
    SelectFieldComponent,
    TimeInputComponent,
  ],
  templateUrl: './new-edition-dialog.component.html',
  styleUrl: './new-edition-dialog.component.scss',
})
export class NewEditionDialogComponent {
  private readonly formats = inject(FormatsApi);
  private readonly events = inject(EventsApi);
  private readonly auth = inject(AuthService);
  private readonly toast = inject(ToastService);
  private readonly i18n = inject(I18nService);

  readonly format = input.required<FormatOut>();
  readonly closed = output<void>();
  readonly created = output<string>();

  protected readonly busy = signal(false);
  protected readonly attempted = signal(false);
  protected readonly orgs = rxResource({
    stream: () => this.events.organizations().pipe(catchError(() => of([] as OrgRef[]))),
  });
  protected readonly orgOptions = computed<SelectFieldOption[]>(() => {
    const own = new Set(this.auth.organizations().map((o) => o.slug));
    const global = this.auth.can('event.read_all');
    return (this.orgs.hasValue() ? this.orgs.value() : [])
      .filter((o) => global || own.has(o.slug))
      .map((o) => ({ value: o.id, label: o.name }));
  });
  protected readonly form = inject(FormBuilder).nonNullable.group({
    organizationId: [''],
    startDate: ['', [Validators.required]],
    startTime: ['', [Validators.required]],
  });

  protected submit(): void {
    this.attempted.set(true);
    if (this.form.invalid || this.busy()) return;
    const v = this.form.getRawValue();
    const body: NewEditionIn = {
      startsAt: zonedToIso(v.startDate, v.startTime, TZID),
      ...(this.orgOptions().length > 1 && v.organizationId && { organizationId: v.organizationId }),
    };
    this.busy.set(true);
    this.formats.newEdition(this.format().slug, body).subscribe({
      next: (out) => {
        this.busy.set(false);
        this.toast.success(this.i18n.translate('format.editionCreated'));
        this.created.emit(out.event.id);
      },
      error: (err: unknown) => {
        this.busy.set(false);
        this.toast.error(problemMessage(this.i18n, problemOf(err)));
      },
    });
  }
}
