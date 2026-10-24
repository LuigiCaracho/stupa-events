/** Spec for the questionnaire state: step order per channel, the interest lock, persistence of answers only, blocked storage. */
import {
  QuestionnaireState,
  consentSentence,
  isPlausibleEmail,
  joinLabels,
} from './questionnaire-state';

const memory = () => {
  const data = new Map<string, string>();
  return {
    data,
    getItem: (k: string) => data.get(k) ?? null,
    setItem: (k: string, v: string) => void data.set(k, v),
    removeItem: (k: string) => void data.delete(k),
  };
};

describe('QuestionnaireState', () => {
  it('starts on the interests step with nothing chosen and locks "Weiter"', () => {
    const s = new QuestionnaireState();
    expect(s.step()).toBe('interests');
    expect(s.interests()).toEqual([]);
    expect(s.canAdvance()).toBe(false);
    s.next();
    expect(s.step()).toBe('interests');
  });

  it('opens with an interest or with meetings', () => {
    const a = new QuestionnaireState();
    a.toggleInterest('party');
    expect(a.canAdvance()).toBe(true);
    const b = new QuestionnaireState();
    b.setMeetings(true);
    expect(b.canAdvance()).toBe(true);
  });

  it('skips the mail step for the calendar channel and adds it for mail', () => {
    const s = new QuestionnaireState();
    expect(s.steps()).toEqual(['interests', 'faculty', 'channel', 'result']);
    expect(s.lastQuestion()).toBe('channel');
    s.setChannel('mail');
    expect(s.steps()).toEqual(['interests', 'faculty', 'channel', 'mail', 'result']);
    expect(s.lastQuestion()).toBe('mail');
  });

  it('keeps the answers when going back', () => {
    const s = new QuestionnaireState();
    s.toggleInterest('party');
    s.next();
    s.setFaculty('fachschaft:fsi');
    s.next();
    s.back();
    s.back();
    expect(s.step()).toBe('interests');
    expect(s.interests()).toEqual(['party']);
    expect(s.faculty()).toBe('fachschaft:fsi');
  });

  it('jumps back to a done step only', () => {
    const s = new QuestionnaireState();
    s.toggleInterest('party');
    s.next();
    s.next();
    s.goTo('interests');
    expect(s.step()).toBe('interests');
    s.goTo('channel');
    expect(s.step()).toBe('interests');
  });

  it('builds the answers for the API', () => {
    const s = new QuestionnaireState();
    s.toggleInterest('party');
    s.setChannel('mail');
    expect(s.answers()).toEqual({
      interests: ['party'],
      meetings: false,
      faculty: null,
      mail: true,
    });
  });

  it('stores only the answers, never the address or the consent', () => {
    const store = memory();
    const s = new QuestionnaireState(store);
    s.toggleInterest('party');
    s.email.set('a@b.de');
    s.consent.set(true);
    s.setChannel('mail');
    const raw = [...store.data.values()].join();
    expect(raw).toContain('party');
    expect(raw).not.toContain('a@b.de');
    expect(raw).not.toContain('consent');
    expect(new QuestionnaireState(store).interests()).toEqual(['party']);
  });

  it('forgets the answers after clearStored', () => {
    const store = memory();
    new QuestionnaireState(store).toggleInterest('party');
    const s = new QuestionnaireState(store);
    s.clearStored();
    expect(new QuestionnaireState(store).interests()).toEqual([]);
  });

  it('ignores a broken stored value and a storage that throws', () => {
    const broken = memory();
    broken.data.set('stupa-events.getstarted', '{nope');
    expect(new QuestionnaireState(broken).interests()).toEqual([]);
    const blocked = {
      getItem: () => {
        throw new Error('blocked');
      },
      setItem: () => {
        throw new Error('blocked');
      },
      removeItem: () => {
        throw new Error('blocked');
      },
    };
    const s = new QuestionnaireState(blocked);
    expect(() => s.toggleInterest('party')).not.toThrow();
    expect(() => s.clearStored()).not.toThrow();
    expect(s.interests()).toEqual(['party']);
  });

  it('drops answers the questionnaire no longer knows', () => {
    const s = new QuestionnaireState();
    s.toggleInterest('party');
    s.toggleInterest('gone');
    s.setFaculty('fachschaft:old');
    s.keepOnly(new Set(['party']));
    expect(s.interests()).toEqual(['party']);
    expect(s.faculty()).toBeNull();
  });
});

describe('text helpers', () => {
  it('joins labels in German', () => {
    expect(joinLabels(['A'])).toBe('A');
    expect(joinLabels(['A', 'B'])).toBe('A und B');
    expect(joinLabels(['A', 'B', 'C'])).toBe('A, B und C');
  });

  it('puts the categories into the consent template', () => {
    expect(consentSentence('Mail zu {categories}.', ['Partys', 'Kino'])).toBe(
      'Mail zu Partys und Kino.',
    );
  });

  it('accepts plausible addresses only', () => {
    expect(isPlausibleEmail('e2e-1@example.test')).toBe(true);
    expect(isPlausibleEmail('nope')).toBe(false);
    expect(isPlausibleEmail('a@b')).toBe(false);
    expect(isPlausibleEmail('a b@c.de')).toBe(false);
  });
});
