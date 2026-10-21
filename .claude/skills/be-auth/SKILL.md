---
name: be-auth
description: Backend identity and access for STUPA Events. OIDC login with PKCE against Authentik or the Keycloak dev IdP, server-side sessions, group-to-role mapping (group_mapping only, effective_grants), membership_sync, session revoke, Principal.has, org_ids_for, require_* gates, /auth/me and CSRF. Use when working on login, callback, logout, sessions, roles, permissions, scope filtering or the 404 rule.
---

<!-- Copied from STUPA-Workflow@93c33d6 .claude/skills/be-auth/SKILL.md (adapted). -->
# Auth: OIDC, sessions, roles: `backend/app/modules/auth`, `backend/app/shared/permissions.py`

**Does:** Logs members in through OIDC (authorization code + PKCE S256) into server-side sessions and derives
roles from the `groups` claim. No JWT ever reaches the browser. Copied from STUPA-Workflow@93c33d6 without the
magic-link and OAuth-AS parts.

## Key files

| File | Role |
|---|---|
| `auth/oidc.py` | discovery (`{issuer}/.well-known/openid-configuration`), PKCE, code exchange, ID-token check |
| `auth/sessions.py` | opaque `sid` in a signed HttpOnly cookie; the row in `auth_session` is the truth |
| `auth/session_renewal.py` | refresh against the IdP every `SESSION_REVALIDATE_HOURS` (4), grace 24 h |
| `auth/rbac.py` | `effective_grants(db, groups)` reads `group_mapping` only; `resolve_principal` uses it; a retired `approver` row grants nothing |
| `admin/membership_sync.py` | writes `membership` (a projection, never read for decisions) after login, revalidation and mapping changes |
| `admin/mappings*.py` | `validate_mapping` (pure), `MappingService`, `/api/admin/group-mappings` incl. `defaults` |
| `auth/principal.py` | `Principal.has(perm, org_id=...)`, `org_slugs_with`, `bind_org_ids` (leaf module, no `app.deps` import) |
| `auth/router.py` | `GET /api/auth/login`, `GET /api/auth/callback`, `POST /api/auth/logout`, `GET /api/auth/me`, `POST /api/auth/sessions/revoke` |
| `shared/permissions.py` | role catalog `ROLE_PERMISSIONS`, `permissions_of`; `parse_group`, `default_mappings` only generate the proposal of `…/defaults` |
| `app/deps.py` | `get_current_principal`, gates `require_principal`, `require_any_scope`, `require_any_permission` |
| `orgs/scope.py` | `bind` (the resolver binds the ids already), `org_refs` (rows for `/auth/me`), `org_ids_for`, `readable_org_ids` |
| `app/middleware.py` | `CsrfMiddleware` (double submit `XSRF-TOKEN` / `X-XSRF-TOKEN`, skips `/api/public/`) |

## Data model

`principal(id, sub, email, display_name, oidc_groups, last_login, active, bootstrap_admin)` and
`auth_session(sid, principal_id, expires_at, refresh_token, id_token, revalidated_at)` from `0001_baseline`;
`group_mapping(oidc_group UNIQUE, role, organization_id NULL)` and `organization(slug, ...)` from
`0002_events_core`; `membership(principal_id, organization_id, role)` and `venue` from `0003_roles_taxonomy`. Users are referenced as OIDC `sub` text in event columns (`created_by`, audit `actor_id`), not as FK.

## API

`GET /api/auth/me` returns `{sub, email, displayName, roles[], permissions[], groups[], organizations[{slug, role,
organizationId, name, short}]}`; 401 `unauthorized` without a session. The organizations come from one query
(`org_refs`), `role` is the effective role.
`POST /api/auth/sessions/revoke` ends all other sessions of the caller; the admin ends all sessions of a person with
`POST /api/admin/principals/{id}/sessions/revoke` (`admin.sessions.revoke`).

Meaning of a group lives in `group_mapping` only (M2, D1). `POST /api/admin/group-mappings/defaults` creates the
proposal: `events-admin|editor|stupa` and `events-<org>-viewer|submitter|organizer` (M5b removed `approver`; migration
0007 renamed old rows to `organizer`). Names starting `events-system:` are dropped from the claim and refused by the API. The org always comes from
the mapping row, never from the body or a query.

Revalidation (4 h, grace 24 h): a refreshed ID token with an empty `groups` array withdraws all groups, a token
without the claim keeps the cache. **Keycloak omits the claim for a user without any group**, so a user who loses
their only group keeps access until the admin revokes the sessions. Real users always sit in `events-users`
(PLAN 5.6), and the dev realm puts every test user there.

## Gotchas

- Never decide on `principal.roles`; always `principal.has(perm, org_id=...)`. A gate on an org-scoped right is
  `require_any_scope(perm)` (`require_principal(perm)` locks out pure org roles).
- No read right means 404, not 403 (no existence oracle). 403 only when the object is visible but the role is short.
- `OIDC_ISSUER` must equal `iss` byte for byte: Authentik ends with `/`, Keycloak does not.
- Cookies are `ev_session`, `ev_oidc_tx` (not `ap_*`): cookies are not port-separated, the Workflow stack on
  `localhost:8080` would clash.
- Host-run dev (`deploy/.env.host.example` copied to `backend/.env`): issuer `http://localhost:8090/...` and callback
  `http://localhost:4200/api/auth/callback`, because browser and host API both reach Keycloak on localhost.
  Containers use `host.docker.internal` plus the `/etc/hosts` line.
- Keycloak sets `AUTH_SESSION_ID` with `Secure` even on http; browsers send it to localhost, scripted clients
  (httpx) do not. `backend/scripts/acceptance_common.py` clears the flag before posting the login form.
- Roles since M5b: org roles `viewer`, `submitter`, `organizer` (`event.publish`, `event.cancel`); global `editor`
  (publishes everything, `event.restore`), `stupa`, `member`, `admin`. The mapping API refuses `approver`.
- The realm users (`editor`, `admin`, `stupa`, `organizer-fsi`, `viewer-fsi`,
  `submitter-fsi`, `submitter-ekhg`, `organizer-makers`, `member`, password `password`) and the client secret are
  throwaways; never reuse them in a real IdP. `scripts/keycloak_admin.py` syncs a running Keycloak with the realm file.
- A test that needs a role writes a `group_mapping` row (`Api.add_user` in the harness); a group name alone grants nothing.

**Tests:** `tests/unit/auth/*`, `tests/unit/admin/*`, `tests/integration/admin/*`, `tests/unit/test_route_authz_inventory.py` (every route has a gate or sits in the
public allowlist), `tests/integration/test_auth_db.py`, `test_rbac_db.py`, `tests/integration/events/test_rbac_matrix.py`.

**Siblings:** `be-events` (scope in queries), `be-lifecycle` (who may publish what), `deploy` (IdP wiring).
