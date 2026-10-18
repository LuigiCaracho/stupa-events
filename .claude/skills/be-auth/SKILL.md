---
name: be-auth
description: Backend identity and access for STUPA Events. OIDC login with PKCE against Authentik or the Keycloak dev IdP, server-side sessions, group-to-role mapping (parse_group, group_mapping), Principal.has, org_ids_for, require_* gates, /auth/me and CSRF. Use when working on login, callback, logout, sessions, roles, permissions, scope filtering or the 404 rule.
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
| `auth/rbac.py` | `resolve_principal`: `group_mapping` first, then `parse_group`; approvers of untrusted orgs drop to organizer |
| `auth/principal.py` | `Principal.has(perm, org_id=...)`, `org_slugs_with`, `bind_org_ids` (leaf module, no `app.deps` import) |
| `auth/router.py` | `GET /api/auth/login`, `GET /api/auth/callback`, `POST /api/auth/logout`, `GET /api/auth/me` |
| `shared/permissions.py` | role catalog `ROLE_PERMISSIONS`, `parse_group`, `grants_from_groups`, `permissions_of` |
| `app/deps.py` | `get_current_principal`, gates `require_principal`, `require_any_scope`, `require_any_permission` |
| `orgs/scope.py` | `bind` (slug to id, one query per request), `org_ids_for`, `readable_org_ids` |
| `app/middleware.py` | `CsrfMiddleware` (double submit `XSRF-TOKEN` / `X-XSRF-TOKEN`, skips `/api/public/`) |

## Data model

`principal(id, sub, email, display_name, oidc_groups, last_login, active, bootstrap_admin)` and
`auth_session(sid, principal_id, expires_at, refresh_token, id_token, revalidated_at)` from `0001_baseline`;
`group_mapping(oidc_group UNIQUE, role, organization_id NULL)` and `organization(slug, trusted, ...)` from
`0002_events_core`. Users are referenced as OIDC `sub` text in event columns (`created_by`, `submitted_by`,
`approved_by`, audit `actor_id`), not as FK.

## API

`GET /api/auth/me` returns `{sub, email, displayName, roles[], permissions[], groups[], organizations[{slug, role}]}`;
401 `unauthorized` without a session. `organizations` comes from `parse_group` alone, without DB.

Group grammar: `^events-(?P<org>[a-z0-9][a-z0-9-]*)-(?P<role>viewer|submitter|organizer|approver)$`, global
`events-editor` (role `editor`), later `events-admin`, `events-stupa`. Names starting `events-system:` and
anything else are dropped. The org always comes from the group name, never from the body or a query.

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
  (httpx) do not. `backend/scripts/m1_acceptance.py` clears the flag before posting the login form.
- Only `stupa` is `trusted` in M1, so `events-fsi-approver` acts as organizer.
- Admin bypass (M2) never skips the hard guards `image_required` and `four_eyes`.
- The realm users (`editor`, `organizer-fsi`, `submitter-fsi`, `organizer-makers`, password `password`) and the
  client secret are throwaways; never reuse them in a real IdP.

**Tests:** `tests/unit/auth/*`, `tests/unit/test_route_authz_inventory.py` (every route has a gate or sits in the
public allowlist), `tests/integration/test_auth_db.py`, `test_rbac_db.py`, `tests/integration/events/test_rbac_matrix.py`.

**Siblings:** `be-events` (scope in queries), `be-pipeline` (who may fire what), `deploy` (IdP wiring).
