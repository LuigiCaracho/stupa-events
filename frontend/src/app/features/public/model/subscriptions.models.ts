/** Wire shapes of the subscription API (B3 contract 3.1 to 3.4): the questionnaire, the profile with its calendar address, the manage page. */

export interface QuestionOption {
  value: string;
  label: string;
}

export interface Question {
  id: string;
  options?: QuestionOption[];
}

export interface ConsentOut {
  version: string;
  template: string;
  privacyUrl: string;
}

export interface QuestionnaireOut {
  version: number;
  questions: Question[];
  consent: ConsentOut;
}

export interface CategoryRef {
  slug: string;
  name: string;
}

export interface ProfileOut {
  icsUrl: string;
  webcalUrl: string;
  categories: CategoryRef[];
}

export interface SubscribeAnswers {
  interests: string[];
  meetings: boolean;
  faculty: string | null;
  mail: boolean;
}

export interface SubscribeIn {
  questionnaireVersion: number;
  answers: SubscribeAnswers;
  email: string | null;
  consent: { version: string; accepted: boolean } | null;
  altcha: string;
}

export interface SubscribeOut {
  profile: ProfileOut;
  mail: { requested: boolean };
}

export interface ConfirmPreviewOut {
  categories: string[];
}

export interface MeOut {
  interests: string[];
  categories: CategoryRef[];
  mailEnabled: boolean;
  icsUrl: string | null;
  hasProfile: boolean;
}

export interface MeUpdate {
  interests?: string[];
  mailEnabled?: boolean;
}

export type RotatedIcsOut = Pick<ProfileOut, 'icsUrl' | 'webcalUrl'>;
