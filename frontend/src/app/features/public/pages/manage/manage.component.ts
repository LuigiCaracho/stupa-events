/**
 * P09 Abo verwalten (`/abo/:token`): the page behind the magic link of a mail. It loads the subscription with the token
 * in a header, lets the person change interests, switch the mail off, make a new calendar address and delete everything.
 * The token leaves the address bar once the subscription is loaded and is never stored (B3 contract 6.4).
 */
import { Location } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  input,
  signal,
} from '@angular/core';
import { rxResource } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { resourceValue } from '@core/api/resource-value';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { NoteComponent } from '@shared/ui/note/note.component';
import { SkeletonComponent } from '@shared/ui/skeleton/skeleton.component';
import {
  ButtonComponent,
  DialogComponent,
  SwitchComponent,
  ToastService,
} from '@stupa-makers/ui-kit';
import { firstValueFrom, throwError } from 'rxjs';
import { HttpErrorResponse } from '@angular/common/http';
import { SubscriptionsApi } from '../../api/subscriptions-api.service';
import { subscriptionErrorOf } from '../../api/subscription-error';
import type { QuestionOption, RotatedIcsOut } from '../../model/subscriptions.models';
import { ChipGroupComponent } from '../../ui/chip-group/chip-group.component';
import { errorText } from '../../ui/error-text';
import { LinkButtonComponent } from '../../ui/link-button/link-button.component';
import { ManageLinkFormComponent } from '../../ui/manage-link-form/manage-link-form.component';
import { usePageTitle } from '../../ui/page-title';
import { ProfileLinksComponent } from '../../ui/profile-links/profile-links.component';

const FACULTY_PREFIX = 'fachschaft:';
const NO_FACULTY = '';

type Phase = 'loading' | 'ready' | 'invalid' | 'failed' | 'deleted';

@Component({
  selector: 'app-manage-page',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    RouterLink,
    TranslatePipe,
    ButtonComponent,
    DialogComponent,
    SwitchComponent,
    NoteComponent,
    SkeletonComponent,
    ChipGroupComponent,
    LinkButtonComponent,
    ManageLinkFormComponent,
    ProfileLinksComponent,
  ],
  templateUrl: './manage.component.html',
  styleUrl: './manage.component.scss',
})
export class ManagePageComponent {
  private readonly api = inject(SubscriptionsApi);
  private readonly i18n = inject(I18nService);
  private readonly toast = inject(ToastService);
  private readonly location = inject(Location);

  readonly token = input<string | undefined>();
  private readonly gone = signal(false);
  private readonly rejected = signal(false);

  private readonly me = rxResource({
    params: () => this.token(),
    stream: ({ params }) =>
      params ? this.api.me(params) : throwError(() => new HttpErrorResponse({ status: 404 })),
  });
  private readonly current = computed(() => resourceValue(this.me, undefined));
  private readonly questions = rxResource({ stream: () => this.api.questions() });

  protected readonly interests = signal<string[]>([]);
  protected readonly faculty = signal<string>(NO_FACULTY);
  protected readonly mailEnabled = signal(false);
  protected readonly busy = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly rotated = signal<RotatedIcsOut | null>(null);
  protected readonly confirmRotate = signal(false);
  protected readonly confirmDelete = signal(false);

  protected readonly phase = computed<Phase>(() => {
    if (this.gone()) return 'deleted';
    if (this.rejected()) return 'invalid';
    if (this.me.isLoading()) return 'loading';
    if (!this.me.error()) return this.current() ? 'ready' : 'loading';
    return subscriptionErrorOf(this.me.error()).kind === 'invalidToken' ? 'invalid' : 'failed';
  });
  protected readonly hasProfile = computed(() => this.current()?.hasProfile ?? false);

  private readonly options = computed(() => {
    const list = resourceValue(this.questions, undefined)?.questions ?? [];
    const of = (id: string): QuestionOption[] => list.find((q) => q.id === id)?.options ?? [];
    return { interests: of('interests'), faculty: of('faculty') };
  });
  protected readonly interestOptions = computed(() => this.options().interests);
  protected readonly facultyOptions = computed<QuestionOption[]>(() => [
    { value: NO_FACULTY, label: this.i18n.translate('public.start.facultyNone') },
    ...this.options().faculty,
  ]);
  protected readonly facultySelected = computed(() => [this.faculty()]);

  private readonly stored = computed(() => this.current()?.interests ?? []);
  protected readonly dirty = computed(() => {
    const current = this.merged();
    const before = this.stored();
    return current.length !== before.length || current.some((s) => !before.includes(s));
  });
  protected readonly canSave = computed(() => this.interests().length > 0 && this.dirty());

  constructor() {
    usePageTitle(() => this.i18n.translate('public.manage.title'));
    effect(() => {
      const me = this.current();
      if (!me) return;
      this.interests.set(me.interests.filter((s) => !s.startsWith(FACULTY_PREFIX)));
      this.faculty.set(me.interests.find((s) => s.startsWith(FACULTY_PREFIX)) ?? NO_FACULTY);
      this.mailEnabled.set(me.mailEnabled);
    });
    effect(() => {
      if (!this.me.isLoading() && this.token()) this.location.replaceState('/abo');
    });
  }

  private merged(): string[] {
    return this.faculty() ? [...this.interests(), this.faculty()] : this.interests();
  }

  protected toggleInterest(slug: string): void {
    this.interests.update((all) =>
      all.includes(slug) ? all.filter((s) => s !== slug) : [...all, slug],
    );
  }

  protected pickFaculty(value: string): void {
    this.faculty.set(value === this.faculty() ? NO_FACULTY : value);
  }

  protected reload(): void {
    this.me.reload();
  }

  protected save(): Promise<void> {
    return this.write({ interests: this.merged() }, () =>
      this.toast.success(this.i18n.translate('public.manage.saved')),
    );
  }

  protected setMail(on: boolean): Promise<void> {
    this.mailEnabled.set(on);
    return this.write({ mailEnabled: on }, () =>
      this.toast.success(this.i18n.translate('public.manage.saved')),
    );
  }

  protected async rotate(): Promise<void> {
    await this.act(async (token) => {
      this.rotated.set(await firstValueFrom(this.api.rotateIcsToken(token)));
      this.confirmRotate.set(false);
    });
  }

  protected async remove(): Promise<void> {
    await this.act(async (token) => {
      await firstValueFrom(this.api.deleteMe(token));
      this.confirmDelete.set(false);
      this.gone.set(true);
    });
  }

  private write(
    body: { interests?: string[]; mailEnabled?: boolean },
    done: () => void,
  ): Promise<void> {
    return this.act(async (token) => {
      const next = await firstValueFrom(this.api.updateMe(token, body));
      this.me.set(next);
      done();
    });
  }

  private async act(run: (token: string) => Promise<void>): Promise<void> {
    const token = this.token();
    if (!token || this.busy()) return;
    this.busy.set(true);
    this.error.set(null);
    try {
      await run(token);
    } catch (err) {
      const failure = subscriptionErrorOf(err);
      this.confirmRotate.set(false);
      this.confirmDelete.set(false);
      if (failure.kind === 'invalidToken') this.rejected.set(true);
      else this.error.set(this.i18n.translate(errorText(failure).key, errorText(failure).params));
    } finally {
      this.busy.set(false);
    }
  }
}
