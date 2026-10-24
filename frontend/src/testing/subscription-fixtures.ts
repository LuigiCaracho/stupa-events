/** Fixtures of the subscription pages (B3): the questionnaire, a profile answer and a manage state. */
import type {
  MeOut,
  QuestionnaireOut,
  SubscribeOut,
} from '../app/features/public/model/subscriptions.models';

export const QUESTIONNAIRE: QuestionnaireOut = {
  version: 1,
  questions: [
    {
      id: 'interests',
      options: [
        { value: 'party', label: 'Partys und Feiern' },
        { value: 'kultur', label: 'Kino, Konzerte, Kultur' },
        { value: 'sitzung', label: 'Sitzungen und Gremien' },
      ],
    },
    { id: 'meetings' },
    { id: 'faculty', options: [{ value: 'fachschaft:fsi', label: 'Fachschaft FSI' }] },
    { id: 'channel' },
    { id: 'mail' },
  ],
  consent: {
    version: '2026-10-1',
    template:
      'Ich möchte wöchentlich eine Mail zu {categories}. Abmelden geht jederzeit mit einem Klick.',
    privacyUrl: '/datenschutz',
  },
};

export const SUBSCRIBED = (mail: boolean): SubscribeOut => ({
  profile: {
    icsUrl: 'https://events.test/ics/p/TOKEN.ics',
    webcalUrl: 'webcal://events.test/ics/p/TOKEN.ics',
    categories: [
      { slug: 'party', name: 'Party' },
      { slug: 'kino', name: 'Kino' },
    ],
  },
  mail: { requested: mail },
});

export const ME: MeOut = {
  interests: ['party', 'fachschaft:fsi'],
  categories: [{ slug: 'party', name: 'Party' }],
  mailEnabled: true,
  icsUrl: null,
  hasProfile: true,
};
