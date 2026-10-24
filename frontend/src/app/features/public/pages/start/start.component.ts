/**
 * P06 Get started (`/start`): a short questionnaire (interests and meetings, faculty, channel, optionally the mail
 * address with the consent) that ends in a personal calendar address and, on request, a double-opt-in mail. The ALTCHA
 * proof is solved when the form is sent. The calendar address of the answer lives only in this component: it is
 * never stored, so a reload starts again at step 1 (B3 contract 6.1).
 */
import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  computed,
  effect,
  inject,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { rxResource } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { resourceValue } from '@core/api/resource-value';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { mediaQuerySignal } from '../../../../layout/media-query';
import { NoteComponent } from '@shared/ui/note/note.component';
import { SkeletonComponent } from '@shared/ui/skeleton/skeleton.component';
import {
  ButtonComponent,
  CheckboxComponent,
  InputComponent,
  MEDIA,
  SegmentedComponent,
  type SegmentedOption,
  type Step,
  StepperComponent,
} from '@stupa-makers/ui-kit';
import { firstValueFrom } from 'rxjs';
import { SubscriptionsApi } from '../../api/subscriptions-api.service';
import { subscriptionErrorOf } from '../../api/subscription-error';
import {
  type Channel,
  QuestionnaireState,
  consentSentence,
  isPlausibleEmail,
} from '../../model/questionnaire-state';
import type { QuestionOption, SubscribeOut } from '../../model/subscriptions.models';
import { AltchaService } from '../../ui/altcha.service';
import { ChipGroupComponent } from '../../ui/chip-group/chip-group.component';
import { errorText } from '../../ui/error-text';
import { LoadErrorComponent } from '../../ui/load-error/load-error.component';
import { usePageTitle } from '../../ui/page-title';
import { ProfileLinksComponent } from '../../ui/profile-links/profile-links.component';

const MEETINGS = 'sitzung';
const NO_FACULTY = '';

function sessionStore(): Storage | null {
  try {
    return window.sessionStorage;
  } catch {
    return null;
  }
}

@Component({
  selector: 'app-start-page',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    FormsModule,
    RouterLink,
    TranslatePipe,
    ButtonComponent,
    CheckboxComponent,
    InputComponent,
    SegmentedComponent,
    StepperComponent,
    NoteComponent,
    SkeletonComponent,
    ChipGroupComponent,
    LoadErrorComponent,
    ProfileLinksComponent,
  ],
  templateUrl: './start.component.html',
  styleUrl: './start.component.scss',
})
export class StartPageComponent {
  private readonly api = inject(SubscriptionsApi);
  private readonly altcha = inject(AltchaService);
  private readonly i18n = inject(I18nService);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);

  protected readonly state = new QuestionnaireState(sessionStore());
  protected readonly questions = rxResource({ stream: () => this.api.questions() });
  protected readonly loaded = computed(() => resourceValue(this.questions, undefined));
  protected readonly phone = mediaQuerySignal(MEDIA.phone);

  protected readonly stepId = this.state.step;
  protected readonly busy = signal(false);
  protected readonly result = signal<SubscribeOut | null>(null);
  protected readonly error = signal<string | null>(null);
  protected readonly emailError = signal('');
  protected readonly consentError = signal(false);

  private readonly options = computed(() => {
    const questions = this.loaded()?.questions ?? [];
    const of = (id: string): QuestionOption[] => questions.find((q) => q.id === id)?.options ?? [];
    return { interests: of('interests'), faculty: of('faculty') };
  });
  protected readonly interestOptions = computed(() =>
    this.options().interests.filter((o) => o.value !== MEETINGS),
  );
  protected readonly facultyOptions = computed<QuestionOption[]>(() => [
    { value: NO_FACULTY, label: this.i18n.translate('public.start.facultyNone') },
    ...this.options().faculty,
  ]);
  protected readonly facultySelected = computed(() => [this.state.faculty() ?? NO_FACULTY]);

  protected readonly yesNo = computed<SegmentedOption[]>(() => [
    { value: 'yes', label: this.i18n.translate('public.start.yes') },
    { value: 'no', label: this.i18n.translate('public.start.no') },
  ]);
  protected readonly channels = computed<SegmentedOption[]>(() => [
    { value: 'calendar', label: this.i18n.translate('public.start.channelCalendar') },
    { value: 'mail', label: this.i18n.translate('public.start.channelMail') },
  ]);

  protected readonly steps = computed<Step[]>(() =>
    this.state
      .steps()
      .map((id) => ({ label: this.i18n.translate(`public.start.step.${id}` as const) })),
  );

  protected readonly consentText = computed(() => {
    const labels = this.chosenLabels();
    return consentSentence(this.loaded()?.consent.template ?? '', labels);
  });
  protected readonly isLastQuestion = computed(
    () => this.state.step() === this.state.lastQuestion(),
  );
  protected readonly lockMessage = computed(
    () => this.state.step() === 'interests' && !this.state.hasInterest(),
  );

  constructor() {
    usePageTitle(() => this.i18n.translate('public.start.title'));
    effect(() => {
      if (!this.loaded()) return;
      const known = [...this.options().interests, ...this.options().faculty].map((o) => o.value);
      this.state.keepOnly(new Set(known));
    });
  }

  protected chosenLabels(): string[] {
    const all = new Map(
      [...this.options().interests, ...this.options().faculty].map((o) => [o.value, o.label]),
    );
    const slugs = [...this.state.interests()];
    if (this.state.meetings() && !slugs.includes(MEETINGS)) slugs.push(MEETINGS);
    const faculty = this.state.faculty();
    if (faculty) slugs.push(faculty);
    return slugs.map((s) => all.get(s) ?? s);
  }

  protected channelValue(value: string | null): void {
    this.state.setChannel((value === 'mail' ? 'mail' : 'calendar') as Channel);
  }

  protected meetingsValue(value: string | null): void {
    this.state.setMeetings(value === 'yes');
  }

  protected pickFaculty(value: string): void {
    this.state.setFaculty(value === NO_FACULTY || value === this.state.faculty() ? null : value);
  }

  protected onStepSelect(index: number): void {
    this.state.goTo(this.state.steps()[index]);
    this.focusHeading();
  }

  protected next(): void {
    this.error.set(null);
    this.state.next();
    this.focusHeading();
  }

  protected back(): void {
    this.error.set(null);
    this.state.back();
    this.focusHeading();
  }

  protected restart(): void {
    this.result.set(null);
    this.state.restart();
    this.focusHeading();
  }

  protected reload(): void {
    this.questions.reload();
  }

  protected async submit(): Promise<void> {
    const questionnaire = this.loaded();
    if (this.busy() || !questionnaire || !this.valid()) return;
    this.busy.set(true);
    this.error.set(null);
    const mail = this.state.channel() === 'mail';
    try {
      const solution = (await this.altcha.solve()) ?? '';
      const out = await firstValueFrom(
        this.api.subscribe({
          questionnaireVersion: questionnaire.version,
          answers: this.state.answers(),
          email: mail ? this.state.email().trim() : null,
          consent: mail ? { version: questionnaire.consent.version, accepted: true } : null,
          altcha: solution,
        }),
      );
      this.state.clearStored();
      this.result.set(out);
      this.state.step.set('result');
      this.focusHeading();
    } catch (err) {
      const { key, params } = errorText(subscriptionErrorOf(err));
      this.error.set(this.i18n.translate(key, params));
    } finally {
      this.busy.set(false);
    }
  }

  private valid(): boolean {
    this.emailError.set('');
    this.consentError.set(false);
    if (this.state.channel() !== 'mail') return true;
    if (!isPlausibleEmail(this.state.email().trim())) {
      this.emailError.set(this.i18n.translate('public.start.emailInvalid'));
      return false;
    }
    if (!this.state.consent()) {
      this.consentError.set(true);
      return false;
    }
    return true;
  }

  private focusHeading(): void {
    queueMicrotask(() =>
      this.host.nativeElement.querySelector<HTMLElement>('[data-step-heading]')?.focus(),
    );
  }
}
