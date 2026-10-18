# Authentik-Anbindung für die lokale Entwicklung

`stupa-events-dev.yaml` legt in Luis' eigenem Authentik (`auth.luismeyer.eu`) den OAuth2-Provider
`stupa-events`, die Application und die vier Rollengruppen an. Das ist **nicht** der Produktiv-Provider
der Hochschule (`sso.reutlingen.university`, PLAN 5.6). Ohne dieses Blueprint läuft die Entwicklung
gegen den Dev-IdP Keycloak (`deploy/docker-compose.keycloak.yml`, Port 8090) mit denselben Gruppen.

Nichts davon ist deployt. Der Ablauf unten ist die Anleitung für `nh os switch`.

## Deploy (Luis)

1. Blueprint ins NixOS-Repo kopieren:
   `cp docs/authentik/stupa-events-dev.yaml ~/.nixos-config/modules/hosts/cloud/authentik-blueprints/`
2. Client-Secret erzeugen und in sops ablegen (`openssl rand -base64 36`), Schlüssel
   `authentik-oauth-stupa-events` in der Cloud-Secrets-Datei.
3. In `modules/hosts/cloud/authentik.nix`:
   - `oidcClients` um `AUTHENTIK_STUPA_EVENTS_CLIENT_SECRET = "authentik-oauth-stupa-events";` ergänzen,
   - `sops.secrets."authentik-oauth-stupa-events".restartUnits = restartAuthentik;` deklarieren (wie bei
     `authentik-oauth-mosaico`).
4. Wie gewohnt auf die Cloud ausrollen: `nh os switch` für den Host `cloud` mit
   `--target-host root@10.66.66.1` und `--use-substitutes`.
5. Im Authentik-Admin prüfen: Application `stupa-events`, Provider `stupa-events` (Scopes openid, email,
   profile, offline_access, `stupa-events groups`), vier Gruppen, vier Policy-Bindings. Fehler eines
   Blueprints stehen nur in `authentik_tasks_tasklog`.
6. Dich selbst in die Gruppen eintragen (UI oder `users.yaml`): `events-editor` für die Redaktion,
   `events-fsi-organizer` oder `events-makers-organizer` für Organisator:innen,
   `events-fsi-submitter` für Einreicher:innen.

## Werte für `deploy/.env.dev` (Authentik statt Keycloak)

| Variable | Wert |
|---|---|
| `OIDC_ISSUER` | `https://auth.luismeyer.eu/application/o/stupa-events/` (mit Schrägstrich am Ende) |
| `OIDC_CLIENT_ID` | `stupa-events` |
| `OIDC_CLIENT_SECRET` | der sops-Wert aus Schritt 2 (nie ins Repo) |
| `OIDC_REDIRECT_URL` | `http://localhost:8081/api/auth/callback` (Compose) oder `http://localhost:4200/api/auth/callback` (`ng serve`) |
| `OIDC_POST_LOGOUT_REDIRECT_URL` | `http://localhost:8081/` |
| `OIDC_SCOPES` | `openid email profile offline_access` |
| `OIDC_GROUPS_CLAIM` | `groups` |
| `BOOTSTRAP_ADMIN_SUBJECTS` | der `sub` aus `GET /api/auth/me` nach dem ersten Login (hängt am Provider) |

Das Compose-Overlay `docker-compose.keycloak.yml` entfällt dann, und `extra_hosts` für
`host.docker.internal` wird nicht gebraucht, weil der Issuer öffentlich auflöst.

## Hinweise

- Der Issuer endet in Authentik **mit** Schrägstrich, in Keycloak ohne. Das Backend vergleicht `iss`
  byte-genau.
- Die Redirect-URIs sind `strict`; ein anderer Port braucht einen weiteren Eintrag im Blueprint.
- Entfernen des Blueprints löscht keine Objekte. Provider und Gruppen bei Bedarf in der UI löschen.
- Der Produktiv-Provider entsteht beim Hochschul-IdP (W2) mit Redirect
  `https://events.reutlingen.university/api/auth/callback` und Policy-Binding auf `events-users`.
