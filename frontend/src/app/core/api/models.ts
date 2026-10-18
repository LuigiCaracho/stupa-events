/** Wire models of the shell endpoints (`/api/auth/*`). Feature models live in `features/**`. */

/** Membership of the principal in one organization, from the group `events-<org>-<role>`. */
export interface OrganizationRole {
  slug: string;
  role: string;
}

/** The signed-in principal (`GET /api/auth/me`). Permissions are UX hints, the server decides. */
export interface Principal {
  sub: string;
  email: string | null;
  displayName: string | null;
  roles: string[];
  permissions: string[];
  groups: string[];
  organizations: OrganizationRole[];
}

/** Result of `POST /api/auth/logout`. `logoutUrl` ends the SSO session at the IdP. */
export interface LogoutResult {
  logoutUrl: string | null;
}

/** RFC 9457 problem detail, with the `reasons[]` extension of the guard answers. */
export interface Problem {
  type?: string;
  title?: string;
  status: number;
  detail?: string;
  code?: string;
  traceId?: string;
  reasons?: ProblemReason[];
}

/** One blocker or warning of a refused transition. `messageKey` is an i18n key. */
export interface ProblemReason {
  code: string;
  field: string | null;
  severity: 'blocker' | 'warning';
  messageKey: string;
  fixAction: 'fill_field' | 'change_date' | 'upload_poster' | null;
}
