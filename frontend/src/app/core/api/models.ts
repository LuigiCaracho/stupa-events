/** Wire models of the shell endpoints (`/api/auth/*`). Feature models live in `features/**`. */

/** Membership of the principal in one organization. */
export interface MeOrganization {
  slug: string;
  role: string;
  organizationId: string;
  name: string;
  short: string;
}

/** The signed-in principal (`GET /api/auth/me`). Permissions are UX hints, the server decides. */
export interface Principal {
  sub: string;
  email: string | null;
  displayName: string | null;
  roles: string[];
  permissions: string[];
  groups: string[];
  organizations: MeOrganization[];
}

/** Result of `POST /api/auth/logout`. `logoutUrl` ends the SSO session at the IdP. */
export interface LogoutResult {
  logoutUrl: string | null;
}

/** RFC 9457 problem detail, with the `reasons[]` extension of `publish_incomplete`. */
export interface Problem {
  type?: string;
  title?: string;
  status: number;
  detail?: string;
  code?: string;
  traceId?: string;
  errors?: ProblemFieldError[];
  reasons?: ProblemReason[];
  /** 409 `conflict`: the current version of the dossier (an `EventDto`, typed by the feature). */
  current?: unknown;
  currentRev?: number;
  /** 413 `file_too_large`: the limit that applies to the upload. */
  limitBytes?: number;
}

/** One field-level validation error of a 409/422 answer. */
export interface ProblemFieldError {
  field: string;
  msg: string;
}

/** One missing piece of a refused publication (`publish_incomplete`): the field that is empty. */
export interface ProblemReason {
  code: string;
  field: string | null;
}
