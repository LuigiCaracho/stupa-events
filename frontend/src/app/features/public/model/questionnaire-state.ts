/**
 * State of the Get-started questionnaire (P06): the answers, the step order and the checks before "Weiter". The
 * answers (never the address, the consent or the result) survive a reload in `sessionStorage`; the result with the
 * calendar token is never stored here, so a reload of the result page starts again at step 1.
 */
import { computed, signal } from '@angular/core';
import type { SubscribeAnswers } from './subscriptions.models';

export type Channel = 'calendar' | 'mail';
export type StepId = 'interests' | 'faculty' | 'channel' | 'mail' | 'result';

export type AnswerStore = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>;

const STORAGE_KEY = 'stupa-events.getstarted';
const MAX_EMAIL_LENGTH = 254;

interface Saved {
  interests: string[];
  meetings: boolean;
  faculty: string | null;
  channel: Channel;
}

export const isPlausibleEmail = (value: string): boolean =>
  value.length <= MAX_EMAIL_LENGTH && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);

/** "a", "a und b", "a, b und c". */
export function joinLabels(labels: readonly string[]): string {
  if (labels.length < 2) return labels.join('');
  return `${labels.slice(0, -1).join(', ')} und ${labels[labels.length - 1]}`;
}

export const consentSentence = (template: string, labels: readonly string[]): string =>
  template.replace('{categories}', joinLabels(labels));

function parse(raw: string | null): Saved | null {
  try {
    const data = JSON.parse(raw ?? 'null') as Partial<Saved> | null;
    if (!data || !Array.isArray(data.interests)) return null;
    return {
      interests: data.interests.filter((i): i is string => typeof i === 'string'),
      meetings: data.meetings === true,
      faculty: typeof data.faculty === 'string' ? data.faculty : null,
      channel: data.channel === 'mail' ? 'mail' : 'calendar',
    };
  } catch {
    return null;
  }
}

export class QuestionnaireState {
  readonly interests = signal<string[]>([]);
  readonly meetings = signal(false);
  readonly faculty = signal<string | null>(null);
  readonly channel = signal<Channel>('calendar');
  readonly email = signal('');
  readonly consent = signal(false);
  readonly step = signal<StepId>('interests');

  readonly steps = computed<StepId[]>(() =>
    this.channel() === 'mail'
      ? ['interests', 'faculty', 'channel', 'mail', 'result']
      : ['interests', 'faculty', 'channel', 'result'],
  );
  readonly stepIndex = computed(() => this.steps().indexOf(this.step()));
  readonly hasInterest = computed(() => this.interests().length > 0 || this.meetings());
  readonly lastQuestion = computed(() => this.steps()[this.steps().length - 2]);

  constructor(private readonly store: AnswerStore | null = null) {
    const saved = parse(this.read());
    if (!saved) return;
    this.interests.set(saved.interests);
    this.meetings.set(saved.meetings);
    this.faculty.set(saved.faculty);
    this.channel.set(saved.channel);
  }

  toggleInterest(slug: string): void {
    this.interests.update((all) =>
      all.includes(slug) ? all.filter((s) => s !== slug) : [...all, slug],
    );
    this.save();
  }

  setMeetings(value: boolean): void {
    this.meetings.set(value);
    this.save();
  }

  setFaculty(value: string | null): void {
    this.faculty.set(value);
    this.save();
  }

  setChannel(value: Channel): void {
    this.channel.set(value);
    this.save();
  }

  keepOnly(known: ReadonlySet<string>): void {
    this.interests.update((all) => all.filter((s) => known.has(s)));
    if (this.faculty() && !known.has(this.faculty() as string)) this.faculty.set(null);
  }

  canAdvance(step: StepId = this.step()): boolean {
    return step !== 'interests' || this.hasInterest();
  }

  next(): void {
    if (!this.canAdvance()) return;
    const steps = this.steps();
    this.step.set(steps[Math.min(this.stepIndex() + 1, steps.length - 1)]);
  }

  back(): void {
    const steps = this.steps();
    this.step.set(steps[Math.max(this.stepIndex() - 1, 0)]);
  }

  goTo(step: StepId): void {
    if (this.steps().indexOf(step) < this.stepIndex()) this.step.set(step);
  }

  restart(): void {
    this.step.set('interests');
  }

  answers(): SubscribeAnswers {
    return {
      interests: this.interests(),
      meetings: this.meetings(),
      faculty: this.faculty(),
      mail: this.channel() === 'mail',
    };
  }

  clearStored(): void {
    try {
      this.store?.removeItem(STORAGE_KEY);
    } catch {
      /* storage may be blocked */
    }
  }

  private read(): string | null {
    try {
      return this.store?.getItem(STORAGE_KEY) ?? null;
    } catch {
      return null;
    }
  }

  private save(): void {
    const saved: Saved = {
      interests: this.interests(),
      meetings: this.meetings(),
      faculty: this.faculty(),
      channel: this.channel(),
    };
    try {
      this.store?.setItem(STORAGE_KEY, JSON.stringify(saved));
    } catch {
      /* storage may be blocked */
    }
  }
}
