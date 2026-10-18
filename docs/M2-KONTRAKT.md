# M2-Kontrakt: Rollen und Organisationen

Verbindlich für die zwei Builder von M2 (**backend**, **frontend**). Quellen: `PLAN.md` §3.3, §3.6, §5, §15.1 (I23, I24, I27), §16.1 (Zeile M2), `ENTSCHEIDUNGEN.md` (E05, E06, E24, E38), `docs/M1-KONTRAKT.md` (gilt weiter, besonders Abschnitt 4.1 Problem+JSON, 5 Scope-Regel, 10 Abweichungen), `docs/M1-ABNAHME.md` (Abschnitt "Offen"), Upstream `STUPA-Workflow@93c33d6` (U) für Muster, `stupa-wp-plugin-phase1/KARTE.md` §2.3, §2.5, §2.6, §9. Pfade `U ...` sind relativ zu `upstream/STUPA-Workflow`.

Stand der Analyse: Branch `feat/m1-durchstich`, Arbeitsbaum ohne M2-Änderungen. Der Branch `feat/m2-rollen` wird erst im letzten Schritt (nach Review) angelegt; bis dahin kein Commit, kein Push. Wo dieser Kontrakt dem PLAN widerspricht, gewinnt der Kontrakt, die Abweichung steht in Abschnitt 10. Was nicht belegt ist, steht als Vorschlag in Abschnitt 9 und wartet auf Luis.

## 1. Lückenanalyse

Jede Zeile ist gegen den Code geprüft (Datei in Klammern), nicht gegen den M1-Kontrakt.

### 1.1 Was aus PLAN §5 und M2 schon existiert

| Teil | Stand in M1 | Beleg |
|---|---|---|
| Berechtigungskatalog §5.3 (Stufe A) | vollständig, 26 Namen; nur die B/D-Rechte (`digest.release`, `subscriber.stats`, `privacy.erase`, `mcp.use`) fehlen bewusst | `shared/permissions.py` |
| Rollen `admin/editor/stupa/member/viewer/submitter/organizer/approver` | alle in `ROLE_PERMISSIONS` | ebd. |
| `Principal.has(perm, org_id)`, `org_slugs_with`, Admin-Bypass, Scope-Deckel | vorhanden, Reihenfolge wie PLAN 5.1 | `auth/principal.py` |
| `approver` nur bei `trusted` (fällt sonst auf `organizer`) | in `resolve_principal`; Test `test_untrusted_org_approver_cannot_approve_but_trusted_can` | `auth/rbac.py` |
| Reservierter Namensraum `events-system:` | verworfen in `clean_groups`, `parse_group` und per DB-CHECK an `group_mapping` | ebd., `0002` |
| `org_ids_for`, `readable_org_ids`, Slug-zu-ID-`bind` (eine Abfrage je Request) | vorhanden, Listen filtern in SQL | `orgs/scope.py`, `events/access.py` |
| 404 statt 403 für unsichtbare Dossiers | `load_visible`; Test `test_foreign_organization_is_invisible` (akzeptiert aber noch `{403, 404}`) | `events/access.py`, `test_rbac_matrix.py` |
| Revalidierung 4 h, Gnadenfrist 24 h, Refresh-Grant, Gruppen-Update aus dem Refresh-ID-Token | vorhanden, Settings `SESSION_REVALIDATE_HOURS`, `..._GRACE_HOURS` | `auth/session_renewal.py` |
| Tabellen `organization`, `group_mapping`, `category` samt CHECKs | seit `0002`; `group_mapping` wird von `resolve_principal` abgefragt | `0002_events_core.py` |
| Organisationen: 13 Zeilen (inkl. `praesidium`), nur `stupa` ist `trusted` | seit `0002`, aus `taxonomy/reference.py` | ebd. |
| Kategorien: 27 Zeilen (22 Bestand + `fachschaft-ls`, `fachschaft-nxt`, `esb-stuco`, `ekhg`, `hochschule`), hierarchisch, `short`/`color_token`/`required_profile` | seit `0002`; Test erwartet 6 Kinder unter `fachschaft` | ebd., `test_lists_and_reference.py` |
| `GET /api/organizations`, `?creatable=true` | **vorhanden** (M1-Abnahme: Frontend rief fälschlich `/api/orgs`) | `orgs/router.py` |
| `GET /api/categories` | **vorhanden**, flach, nur `{id, slug, name, kind}` | `taxonomy/router.py` |
| `organization_slug` in `public_event_v` und Feed-Filter `?org=` | View-Spalte **vorhanden**; es fehlt nur `slug` im Feed-Objekt `organization` | `0002` (View), `publicapi/service.py:45,123` |
| Routen-Inventur | vorhanden; scheitert bei Route ohne Gate und bei Public-Route mit Session | `tests/unit/test_route_authz_inventory.py` |
| `end_principal_sessions` | vorhanden, aber von keiner Route benutzt | `auth/sessions.py:186` |
| `AuditAction.ROLE_MAPPING_CHANGE`, `SESSION_REVOKE`, `CONFIG_CHANGE` | vorhanden, ungenutzt | `audit/actions.py` |
| Keycloak-Realm mit 4 Nutzern | vorhanden (`editor`, `organizer-fsi`, `submitter-fsi`, `organizer-makers`) | `deploy/keycloak/stupa-events-realm.json` |

### 1.2 Was fehlt

| # | Lücke | Wirkung | Abschnitt |
|---|---|---|---|
| L1 | **Keine API für `group_mapping`.** PLAN 5.6 und M1-Abweichung 7: "Namen stehen nur in `group_mapping`, nie im Code" gilt ab M2. Heute entscheidet `parse_group` (Gruppenname im Code) und `group_mapping` ergänzt nur. | I24 nicht baubar; Gruppenumbenennung in Authentik bricht still | 2.4, 4, 9 (D1) |
| L2 | **Kein `membership_sync`.** PLAN 3.3: Tabelle `membership(principal_id, organization_id, role)`, "nur der Sync schreibt". Die Tabelle existiert nicht. Rechte werden bei jedem Request aus `principal.oidc_groups` aufgelöst, das ist korrekt, liefert aber keine Mitgliederliste je Organisation (M4: Aufgaben zuweisen, Mails an die Org) und keinen Audit-Eintrag bei Rollenwechsel. | Mitglieder je Org nicht abfragbar | 3, 4 |
| L3 | **Sync-Hooks:** `upsert_principal` ist der gemeinsame Punkt für Login (`oidc_callback`) und Revalidierung (`renew_principal_session`); dort fehlt jeder Sync-Aufruf. | | 4 |
| L4 | **Revalidierung nie gegen den echten IdP bewiesen.** Der Code hält die gecachten Gruppen, wenn der Refresh-Token den `groups`-Claim **weglässt** (`oidc.py:366`). Entfernt Keycloak den Claim bei Nutzern ohne Gruppe, bleibt ein entzogenes Recht für immer. | M2-Kriterium "Entfernen einer Gruppe entzieht Zugriff" | 6, 9 (D2) |
| L5 | **Rolle `admin` hat `taxonomy.manage` und `import.manage`, aber nicht `venue.manage`.** PLAN 5.2: Admin pflegt "Taxonomie"; Orte gehören dazu (I23). | Admin kann keine Orte pflegen, ohne Bypass-Zufall | 2.3 |
| L6 | **Keine Admin-API für Kategorien, Orte, Organisationen.** | I23 nicht baubar | 2.3 |
| L7 | **Tabelle `venue` fehlt komplett** (nur `event.venue_text`). Die Aufgabe nennt "venue mit Adresse/GPS-Spalten nullable": die Tabelle ist neu, nicht erweitert. `event.venue_id` kommt **nicht** in M2 (Abschnitt 9, D4). | 44 Orte ohne Zielort | 3 |
| L8 | **Kategorie-Slugs weichen vom Altbestand ab** (`lan-party` statt `lanparty`, `fachschaft-fsi` statt `fachschaft-informatik-fsi`, `-tec`, `-tex`, `fachschaft-ls` statt `fachschaft-life-sciences-ls`). KARTE §9: "Bestehende Slugs/URLs bleiben". Die Slugs erscheinen im öffentlichen Feed (`categories[].slug`, Filter `?category=`). M1 hat die Abweichung nicht in Abschnitt 10 geführt. | WordPress-/Astro-Archive und Mapping brechen | 3.3, 9 (D3) |
| L9 | **Datenfehler:** Organisation `tec` trägt `legacy_wp_ids = {174}`; 174 ist die ID der **Kategorie** (KARTE §2.3). KARTE §2.6: "Kein Organizer für Fachschaft TEC". | falsche Zuordnung beim Import (M6) | 3.3 |
| L10 | **Kein "Sitzungen widerrufen"** (eigene und für andere). | E24, I24, I27 | 2.5 |
| L11 | **`GET /api/auth/me` liefert Organisationen nur als `{slug, role}`**, ohne Name, Kürzel, `trusted`. Die Skill-Doku `be-auth` sagt fälschlich "ohne DB"; der Code nimmt `principal.organizations` aus dem aufgelösten Principal (inkl. Mappings). | UI zeigt Slugs | 2.6 |
| L12 | **Feed-Objekt `organization` ohne `slug`.** Die View hat die Spalte, der Konsument kann `?org=` nicht aus der Antwort bilden. | | 2.7 |
| L13 | **Inventur zu schwach:** (a) `require_principal()` ohne Recht zählt als Gate, eine Route ohne jede Prüfung besteht also mit einem Handgriff; (b) `EXPECTED_GATE_PERMS` deckt drei Routen, alle anderen sind nur "irgendein Gate"; (c) kein Test, dass der Test selbst eine ungesicherte Route erkennt. | PLAN 5.5, M2-Kriterium 4 | 7 |
| L14 | **Matrix-Test unvollständig:** keine Zeilen für `admin`, `stupa`, `member`, `submitter-ekhg` (Partner), kein Zeile `approver` einer vertrauten Org außer als Einzeltest; `FOREIGN` akzeptiert `{403, 404}` statt exakt 404; keine M2-Routen. | M2-Kriterium 1 und 2 | 6 |
| L15 | **Sichtbarkeitstabelle §5.4 (Dossier-Ebene)** hat keinen eigenen Test (`test_visibility`, PLAN 12.1). | | 6 |
| L16 | **Keycloak-Realm** kennt weder `admin`, `stupa`, `member`, `viewer`, `approver` noch einen Partner (ekhg). PLAN 3.6 verlangt je einen Testnutzer für `admin`, `editor`, `stupa`, FSI-`organizer`, ekhg-`submitter`, `member`. | Abnahme ohne Nutzer | 2.8 |
| L17 | **`coverage_critical.py` fehlt.** M1-Abweichung 5 verschob die 100-%-Branch-Pflicht für `auth, audit, files, media` auf M2, "wenn die Module nicht mehr nur kopiert sind". `auth` wird in M2 geändert. | Gate fehlt | 6 |
| L18 | **Doppelte Sicherheits-Header auf `/api/*`:** nginx (`security-headers.conf`) **und** die API (`middleware.py`) setzen beide `Content-Security-Policy`, `Permissions-Policy`, `Referrer-Policy` (mit **verschiedenen** Werten: `no-referrer` gegen `strict-origin-when-cross-origin`), `X-Content-Type-Options`, `X-Frame-Options`. `smoke.sh` prüft nur "mindestens eine CSP". | M1-Rest | 6 |
| L19 | **5 `tsc`-Fehler** unter `tsconfig.spec.json` (`npm run typecheck` prüft nur `tsconfig.app.json` und sieht sie nicht): `shared/truncated.directive.spec.ts(64)`, `shared/ui/select/select.component.spec.ts(518,519)`, `testing/a11y.ts(14,39)` (letzteres zwei Fehler, `jest-axe`-Typen). | M1-Rest | 6 |
| L20 | `GroupMapping`/`membership` brauchen `DELETE` für `events_app`; `0002` entzieht es für `group_mapping` ausdrücklich (`_GRANTS`), `roles.sql` Stufe 2 nennt es nicht. | Löschen scheitert mit `InsufficientPrivilege` | 3.4 |

## 2. API-Vertrag M2

Alle Pfade unter `/api`. Konventionen wie M1: camelCase (`CamelModel`, `extra="forbid"`), Zeiten ISO-8601 mit Offset, Fehler ausnahmslos `application/problem+json` mit den Codes aus M1 4.1. **Gate-Regel:** ein fehlendes Routenrecht antwortet 403 `forbidden`, unabhängig von der Objekt-ID; 404 `not_found` gibt es erst, wenn das Gate besteht und das Objekt für den Aufrufer nicht lesbar ist (Dossiers) oder nicht existiert. Zustandsändernde Routen laufen mit CSRF (`X-XSRF-TOKEN`), der Router committet, Audit in derselben Transaktion.

### 2.1 Typen

```
OrgRef          { id, slug, name, short }                                  # unverändert (M1)
CategoryOut     { id, slug, name, kind, parentId|null, short|null, colorToken|null,
                  requiredProfile, sort }                                  # nur aktive Kategorien
CategoryNode    CategoryOut + { children: CategoryNode[] }                 # ?tree=true
VenueRef        { id, slug, name, address|null, postcode|null, city|null,
                  buildingNo|null, roomKey|null }                          # nur aktive Orte; bei isPrivate sind
                                                                           # address, postcode, city null
AdminOrganization { id, slug, name, kind, short, parentId|null, colorToken|null, categoryId|null,
                  instagram[], trusted, legacyWpIds[], active, createdAt, updatedAt }
AdminCategory   { id, slug, name, kind, parentId|null, short|null, colorToken|null, requiredProfile,
                  legacyWpId|null, sort, active, createdAt, updatedAt }
AdminVenue      { id, slug, name, address|null, postcode|null, city|null, buildingNo|null,
                  roomKey|null, campusBuildingNo|null, lat|null, lon|null,
                  publicPrecision: "exact"|"building"|"hidden", isPrivate, geocodeSource|null,
                  geocodedAt|null, legacyWpId|null, notes|null, active, createdAt, updatedAt }
GroupMappingOut { id, oidcGroup, role, organization: OrgRef|null, principalCount, createdAt, updatedAt }
AdminPrincipal  { id, sub, displayName|null, email|null, groups[], lastLogin|null, active, sessionCount }
MeOrganization  { slug, role, organizationId, name, short, trusted }
RevokeResult    { revoked: int }
```

`kind`, `requiredProfile`, `colorToken` sind Enums: `CategoryOut.kind ∈ format|fachschaft|partner`; Organisation `kind ∈ stupa|referat|fachschaft|partner|hochschule|redaktion`; `requiredProfile ∈ generic|party|meeting|trip`; `colorToken ∈ orange|blue|petrol|navy|yellow|red` (Konstante `COLOR_TOKENS`, Quelle `astro.md:89`, nie Hex). Slugs: `^[a-z0-9][a-z0-9-]{0,59}$`. Ein Slug ist **unveränderlich** (er steht im Feed, in `?org=`, `?category=` und in Archiv-URLs): `PATCH` mit `slug` antwortet 422 `validation_error` (`extra="forbid"`).

### 2.2 Lesen (jede angemeldete Person, Gate `library.read`)

| Methode Pfad | Antwort | Anmerkung |
|---|---|---|
| `GET /api/organizations` | `OrgRef[]` | aktive, nach Name; `?creatable=true` nur Orgs mit `event.create` für den Aufrufer (M1, unverändert) |
| `GET /api/categories` | `CategoryOut[]` | aktive, nach `kind`, `sort`, `name`; `?tree=true` liefert `CategoryNode[]` (Wurzeln: Kategorien ohne Eltern). Das M1-Feld-Set `{id, slug, name, kind}` wächst additiv; `test_category_list` wird angepasst |
| `GET /api/venues` | `VenueRef[]` | aktive, nach Name |

### 2.3 Taxonomie verwalten (Gate je Route)

Referenzdaten ändern sich selten; kein `rev`, letzter Schreiber gewinnt. **Kein `DELETE`**: Organisationen, Kategorien und Orte werden nie gelöscht, nur mit `active=false` ausgeblendet (PLAN 3.3; `events_app` hat auf diese Tabellen kein `DELETE`). Jede Mutation schreibt `audit_entry` mit `AuditAction.CONFIG_CHANGE`, `target_type ∈ organization|category|venue`, `data` mit Feldnamen der Änderung, nie Werte mit Personenbezug.

| Methode Pfad | Recht | Request | Antwort / Fehler |
|---|---|---|---|
| `GET /api/admin/organizations` | `taxonomy.manage` | | `AdminOrganization[]` inkl. inaktive |
| `POST /api/admin/organizations` | `taxonomy.manage` | `{slug, name, kind, short, parentId?, colorToken?, categoryId?, instagram?, active?, trusted?}` | 201 `AdminOrganization`; 409 `slug_taken`; 422 bei unbekanntem `parentId`/`categoryId` |
| `PATCH /api/admin/organizations/{id}` | `taxonomy.manage` | alle Felder optional außer `slug`; `trusted` nur mit `admin.mappings` | 200; **`trusted` ohne `admin.mappings`: 403 `forbidden`** (auch beim Anlegen), 404 unbekannte ID |
| `GET/POST/PATCH /api/admin/categories[/{id}]` | `taxonomy.manage` | `{slug, name, kind, parentId?, short?, colorToken?, requiredProfile?, sort?, active?}` | wie oben; 422 `category_cycle` (Eltern-Kette), 409 `slug_taken` |
| `GET/POST/PATCH /api/admin/venues[/{id}]` | `venue.manage` | `{slug, name, address?, postcode?, city?, buildingNo?, roomKey?, campusBuildingNo?, lat?, lon?, publicPrecision?, isPrivate?, notes?, active?}` | `lat` und `lon` nur zusammen (422 `coordinates_incomplete`), `-90..90`/`-180..180`, `numeric(9,6)`; wer sie von Hand setzt, setzt `geocodeSource='pin'` und `geocodedAt=now`; Löschen beider setzt beide Felder `null` |

Wirkung von `trusted`: Es ändert die aufgelösten Rechte aller Approver der Organisation. Die Route ruft danach `sync_all_memberships` (Abschnitt 4) in derselben Transaktion und schreibt zusätzlich `AuditAction.ROLE_MAPPING_CHANGE` (`target_type=organization`, `data={trusted: bool}`).

### 2.4 Gruppen-Zuordnung (Gate `admin.mappings`)

| Methode Pfad | Request | Antwort / Fehler |
|---|---|---|
| `GET /api/admin/group-mappings` | | `GroupMappingOut[]`, nach `oidcGroup`; `principalCount` = Personen, deren gecachte `oidc_groups` die Gruppe enthalten |
| `POST /api/admin/group-mappings` | `{oidcGroup, role, organizationId?}` | 201 `GroupMappingOut` |
| `PATCH /api/admin/group-mappings/{id}` | `{role?, organizationId?}` (`oidcGroup` ist unveränderlich: umbenennen heißt löschen und neu anlegen) | 200 |
| `DELETE /api/admin/group-mappings/{id}` | | 204 |
| `POST /api/admin/group-mappings/defaults` | leer | 200 `GroupMappingOut[]` der **neu angelegten** Zeilen (idempotent): `events-admin→admin`, `events-editor→editor`, `events-stupa→stupa` und je aktiver Organisation `events-<slug>-viewer|submitter|organizer` (PLAN 5.6, Gruppen-Vorschlag W2); `events-<slug>-approver` **nur** für `trusted` Organisationen |
| `GET /api/admin/principals` | Query `group?`, `organizationId?`, `q?`, `limit` (1..200, 50), `offset`; Gate `admin.mappings` oder `admin.sessions.revoke` | `Page<AdminPrincipal>`; `organizationId` filtert über die Tabelle `membership` |

Validierung (alle 422 Problem+JSON mit `code` und `errors[{field,msg}]`; die deutschen Texte stehen in I24):

| `code` | Bedingung | Text in I24 |
|---|---|---|
| `reserved_group_prefix` | `oidcGroup` beginnt mit `events-system:` | "Gruppe beginnt mit reserviertem Präfix events-system:." |
| `organization_required` | Rolle ∈ `viewer|submitter|organizer|approver` ohne `organizationId` | "Org-Rolle braucht eine Organisation." |
| `organization_forbidden` | globale Rolle mit `organizationId` | "Globale Rolle gilt ohne Organisation." |
| `approver_requires_trusted` | Rolle `approver`, Organisation nicht `trusted` | "Approver nur in vertrauten Organisationen." |
| `implicit_role` | Rolle `member` (jede angemeldete Person hat sie) | "Die Rolle member gilt für alle Angemeldeten." |
| `unknown_organization` | `organizationId` existiert nicht oder ist inaktiv | "Organisation nicht gefunden." |

409 `duplicate_group` bei zweiter Zeile für dieselbe Gruppe (`UNIQUE oidc_group`). 409 `last_admin_mapping`, wenn Löschen oder Ändern die letzte Zeile mit Rolle `admin` entfernt **und** `BOOTSTRAP_ADMIN_SUBJECTS` und `..._EMAILS` leer sind (Aussperrschutz; Vorschlag, Abschnitt 9 D5). Der Validator ist eine reine Funktion `validate_mapping(role, organization) -> list[FieldError]` in `app/modules/admin/mappings.py`. Der DB-CHECK (`0002`) bleibt das zweite Netz; `approver`-Vertrauen prüft die API zusätzlich zur Laufzeit-Rückstufung in `resolve_principal` (Vertrauen kann später entfallen, dann fällt der Approver auf `organizer` zurück, die Zeile bleibt).

Jede Mutation: `sync_all_memberships` in derselben Transaktion, Audit `ROLE_MAPPING_CHANGE` (`target_type=group_mapping`, `target_id`, `data={oidcGroup, role, organizationId}`; Gruppennamen sind keine Personendaten).

### 2.5 Sitzungen widerrufen

| Methode Pfad | Recht | Wirkung |
|---|---|---|
| `POST /api/auth/sessions/revoke` | Session (`require_principal()`, steht in `SESSION_ONLY_ALLOWLIST`, Abschnitt 7) | beendet alle **anderen** Sitzungen der aufrufenden Person; die laufende bleibt. 200 `RevokeResult` |
| `POST /api/admin/principals/{id}/sessions/revoke` | `admin.sessions.revoke` | beendet **alle** Sitzungen der Person (`sessions.end_principal_sessions`). 200 `RevokeResult`; 404 unbekannte Person |

Audit `SESSION_REVOKE`, `target_type=principal`, `target_id=<principal.id>`, `data={scope: "own"|"admin", count: n}`. Eine beendete Sitzung ist nicht das Entziehen von Rechten: Rechte kommen aus den Gruppen des IdP und werden beim nächsten Login frisch gelesen. Der Knopf erzwingt diesen Login sofort (Gnadenfrist-Umgehung nach Entzug im IdP). Neue Funktion `sessions.end_other_principal_sessions(db, principal_id, keep_sid)`.

### 2.6 `GET /api/auth/me` (erweitert)

`Me` aus M1 4.2 bekommt `organizations: MeOrganization[]` statt `{slug, role}`. `role` ist die **wirksame** Rolle (ein `approver` einer nicht vertrauten Org erscheint als `organizer`, `trusted=false`). Die Organisationsdaten kommen aus **einer** Abfrage (`orgs/scope.py: org_refs(session, principal)`, dieselbe Abfrage wie `bind`), `permissions` und `roles` bleiben unverändert. Das Feld `groups` bleibt (Konto zeigt es, I27). `m1_acceptance.py` (A1: `orgs [{'slug': 'fsi', 'role': 'organizer'}]`) vergleicht künftig die Teilmenge `slug`/`role`.

### 2.7 Öffentlicher Feed

`PublicOrganization` wird `{id, slug, name, short}`; `tests/schema/feed-v2.json` verlangt `slug` (`required`, Muster wie 2.1). Die View `public_event_v` ändert sich **nicht**. Keine weitere öffentliche Änderung in M2; Kontaktdaten bleiben draußen.

### 2.8 Testnutzer im Dev-IdP (`deploy/keycloak/stupa-events-realm.json`)

Passwort wie M1 `password`, `email = <name>@example.test`, `emailVerified=true`. Neue Nutzer und Gruppen (Gruppen werden mit `defaults` aus 2.4 und von `seed_dev` als Mappings angelegt):

| Nutzer | Gruppe | Zweck |
|---|---|---|
| `admin` | `events-admin` | Verwaltung, Sitzungen anderer widerrufen |
| `stupa` | `events-stupa` | liest alles, schreibt nichts |
| `approver-stupa` | `events-stupa-approver` | vertrauter Approver |
| `approver-fsi` | `events-fsi-approver` | Approver ohne Vertrauen (wird `organizer`) |
| `viewer-fsi` | `events-fsi-viewer` | nur lesen |
| `submitter-ekhg` | `events-ekhg-submitter` | **Partner-Testkonto** (PLAN 3.6) |
| `member` | (keine) | nur `member` |

Bestand bleibt: `editor`, `organizer-fsi`, `submitter-fsi`, `organizer-makers`. Die Datei gehört dem Backend-Builder (gleiche Abnahme-Skripte); `BOOTSTRAP_ADMIN_SUBJECTS` bleibt im Dev leer, damit `admin` seine Rolle nachweislich **per Gruppe** erhält.

## 3. Datenmodell-Delta (Migration `0003_roles_taxonomy`)

Eine Revision, `down_revision = "0002_events_core"`, genau ein Head, ID ≤ 32 Zeichen. `0002` wird **nicht** geändert (Alembic-Policy der Skill `conventions`: expand/contract). Läuft auf frischer DB und auf einer M1-Datenbank (`test_migrations`: beide Wege enden im selben Schema und denselben Referenzzeilen).

### 3.1 `venue` (neu)

```
venue(id uuid pk default gen_random_uuid(), slug text unique not null, name text not null,
      address text, postcode text, city text, building_no text, room_key text,
      campus_building_no text, lat numeric(9,6), lon numeric(9,6),
      public_precision text not null default 'hidden' check in (exact, building, hidden),
      is_private bool not null default false,
      geocode_source text check in (pin, nominatim, import) or null, geocoded_at timestamptz,
      legacy_wp_id int, notes text, active bool not null default true,
      created_at, updated_at timestamptz not null default now())
CHECK (lat IS NULL) = (lon IS NULL)
CHECK lat BETWEEN -90 AND 90 AND lon BETWEEN -180 AND 180
CHECK name, address, notes ohne Steuerzeichen (gleiches Muster wie ck_event_venue_text_clean)
```

PLAN 3.3 nennt `room_key` "normalisiert (`9-229`, `9-u9`)": Funktion `normalize_room_key(text) -> str | None` (klein, ohne "Raum", führende Nullen der Zimmernummer entfallen: `9-U09` wird `9-u9`) in `taxonomy/venues.py`, reine Funktion, hypothesis-Test. Standard `public_precision='hidden'`: nichts wird öffentlich, bevor jemand es bewusst setzt (passt zu M1-Abweichung 4; Stufe C pflegt Koordinaten, PLAN 16.3 C2).

### 3.2 `membership` (neu)

```
membership(principal_id uuid not null fk principal on delete cascade,
           organization_id uuid not null fk organization on delete cascade,
           role text not null check in (viewer, submitter, organizer, approver),
           created_at timestamptz not null default now(),
           primary key (principal_id, organization_id, role))
index (organization_id, role)
```

Eine Person kann in einer Org mehrere Rollen halten (zwei Gruppen); der Sync speichert die **wirksamen** Rollen nach Rückstufung (4). Entscheidungen fallen nie aus dieser Tabelle, sondern aus `Principal.has` (sonst könnte eine veraltete Zeile Rechte geben); sie dient Listen, Zuweisung (M4) und der Vorschau.

### 3.3 Referenzdaten

Alle Ids bleiben `uuid5` des **M1-Schlüssels** (`reference_id("category", "<M1-Slug>")`), damit bestehende Zeilen und Fremdschlüssel stabil bleiben. Neues Modul `taxonomy/reference_m2.py` (Änderungen als Daten, `0002` und `reference.py` bleiben unberührt). `0003` und `ensure_reference` wenden es idempotent an (`UPDATE ... WHERE id = :id`, `INSERT ... ON CONFLICT DO NOTHING`).

| Änderung | Inhalt | Beleg |
|---|---|---|
| Kategorie-Slugs | `lan-party`→`lanparty`, `fachschaft-fsi`→`fachschaft-informatik-fsi`, `fachschaft-tec`→`fachschaft-technik-tec`, `fachschaft-tex`→`fachschaft-texoversum-tex`, `fachschaft-ls`→`fachschaft-life-sciences-ls` (`fachschaft-nxt` und `esb-stuco` bleiben). Namen bleiben wie in M1. Folgen: `backend/seeds/dev_events.yaml`, `m1_acceptance.py`, Tests und E2E suchen nach den vier alten Slugs und ziehen nach | KARTE §2.3, §9 (Entscheidung D3) |
| `organization.tec.legacy_wp_ids` | `{174}` wird `{}` | KARTE §2.3, §2.6 |
| Kategorien | bleibt bei 27 Zeilen (22 Bestand + 5 neu: `fachschaft-life-sciences-ls`, `fachschaft-nxt`, `esb-stuco`, `ekhg`, `hochschule`); Eltern `fachschaft` mit 6 Kindern; `typ`/`kurz`/`farbe` heißen im Schema `kind`/`short`/`color_token`; Farben `petrol, red, yellow, orange, blue, navy` | PLAN 3.3, KARTE §9 |
| Organisationen | bleibt bei 13 Zeilen: `stupa, makers, fsi, tec, tex, ls, nxt, esb-stuco, ekhg, hochschule, praesidium, oikos, care`; **nur `stupa` ist `trusted`** (E05 nennt "Start: keine Organisation trusted"; M1 setzt `stupa` als Ausnahme, die Zeile bleibt, Entscheidung D8); `praesidium` bleibt, weil PLAN 3.3 und KARTE §2.6 es führen | PLAN 3.3, E05 |
| 44 Orte | Modul `taxonomy/venue_reference.py` mit `VENUES` (Tupel von Dicts, `id = reference_id("venue", slug)`, `legacy_wp_id` = WP-Post-ID aus KARTE §2.5). Genau diese 44 Namen: 1932 Kinosaal 9-133, 1648 Fakultät Informatik, 2006 Students Hut, 2565 Präsidium Gebäude 3, 2377 Maker Space 9-229, 2059 FSI 9-U09, 1639 Hochschule Reutlingen, 2322 Texoversum, 2319 Stupa Büro, 2277 Zum alten Rappen, 1595 JAZZclub in der Mitte, 2032 Senatssaal, 2433 Raum 5-015, 2355 Raum 17-U14, 2411 Campus Reutlingen Building 17, 2367 Geb. 17 Pavillon, 1989 Aula Building 6, 1981 Maschinenhalle Geb. 1, 2363 Rasen zwischen Geb. 3 und Geb. 1, 2648 Davos, 2645 Schwarzwald, 2642 Serfaus-Fiss-Ladis, 2639 Arosa-Lenzerheide, 1813 Flumserberg, 1810 Montafon, 1805 Ischgl, 2579 Rosengarten Pomologie, 2441 Kart & Fun Neckartenzlingen, 2393 Europapark, 2390 in the air, 2386 Am Kreuzeichenstadion, 2382 Göckelesmaier Festzelt, 2198 Hades, 2056 franz.K, 2020 Arcadia, 2000 Schwarzen Schaf, 1796 Jugend-Hüttendorf Vulkaneifel, 1729 The mad coyote, 1643 Straßburg, 1632 Eishalle Reutlingen, 1625 Jugenddorf Teufelsfels, 1621 Festzelt Fürstenberg, 1612 FSC Calw e.V., 1579 Extrial Campusfest 2025 | KARTE §2.5, `wp-live.md` §3.8 |

**Adressen: nur, was die Quelle nennt.** `wp-live.md` §3.8 gibt Anschriften für: 1932 und 1648 Pestalozzistraße 62, 2006 Pestalozzistraße 52, 2565 und 1639 Alteburgstraße 150, 2322 Gebäude 30 (Quelle "Altenburgstraße": bereinigt zu "Alteburgstraße", Hausnummer unbekannt, Hinweis in `notes`), 2277 Ob. Gerberstraße 6, 2642 Gänsackerweg 2 (Serfaus), 2579 Friedrich-Ebert-Straße 12 (Reutlingen), 2393 (Rust), 2382 (Cannstatter Wasen), 2000 (Tübingen). Alle übrigen Orte haben `address = NULL`, nichts wird nachrecherchiert. `building_no` und `room_key` leitet der Seed **nur aus dem Namen** ab (`9-133` → Gebäude `9`, `room_key` `9-133`; `9-U09` → `9-u9`; `9-229`, `5-015`, `17-U14`; `Senatssaal Raum 5003` bleibt ohne Schlüssel). Slug-Regel: `slugify(name)` (Umlaute `ä→ae` usw.), Tippfehler des Altbestands bereinigt (`kinosaal-9-133` statt `kinosaal-9-113`, `maschinenhalle-geb-1`, `rasen-zwischen-geb-3-und-geb-1`, `aula`); Eindeutigkeit prüft `test_venue_reference`. `lat`/`lon` bleiben `NULL`, `is_private=false`, `public_precision='hidden'`.

### 3.4 Rechte der DB-Rollen

`0003` bleibt wie `0002` (`events_app` per Default `SELECT, INSERT, UPDATE`; `events_public` nichts). `deploy/db/roles.sql` Stufe 2 nimmt `group_mapping` und `membership` in die `DELETE`-Liste auf; `venue` bekommt **kein** `DELETE`. `test_db_grants.py` (Besitzer backend) führt dieselbe Liste und prüft: `events_app` kann `DELETE FROM group_mapping`, `DELETE FROM membership`, nicht `DELETE FROM venue`, `organization`, `category`; `events_public` liest `venue` nicht.

### 3.5 Nicht in `0003`

`principal.last_revalidated_at` entfällt: der Zeitpunkt steht in `auth_session.revalidated_at` (je Sitzung, `0001`) und das reicht für 4 h/24 h. `event.venue_id` und ein Orts-Auswahlfeld im Dossier folgen mit M3 (Entscheidung D4). Kein Index auf `principal.oidc_groups` (wenige hundert Personen; Abfrage `oidc_groups @> to_jsonb(:g)`).

## 4. `membership_sync` und Auflösung

Eine einzige Funktion berechnet die wirksamen Rollen; Auflösung und Sync benutzen sie beide, damit sie nicht auseinanderlaufen.

```
effective_grants(db, groups: set[str]) -> EffectiveGrants   # app/modules/auth/rbac.py
  global_roles: set[str]                    # ohne member, ohne bootstrap admin
  org_roles:    dict[slug, set[role]]       # nach Rückstufung
```

1. `groups = clean_groups(principal.oidc_groups)` (verwirft `events-system:`).
2. **Nur `group_mapping` entscheidet** (Entscheidung D1): `SELECT role, organization.slug FROM group_mapping LEFT JOIN organization WHERE oidc_group IN groups`. Die Zeile gilt nur, wenn (`slug IS NULL` und Rolle global) oder (`slug` gesetzt und Rolle org-gebunden); Zeilen zu **inaktiven** Organisationen entfallen nicht (Dossiers bleiben lesbar), nur das Anlegen ist gesperrt (`EventService.create` prüft `active`, M1).
3. Rückstufung: Rolle `approver` in einer Org mit `trusted=false` zählt als `organizer` (E05).
4. Globale Rollen = `{member}` ∪ aus Schritt 2 ∪ (`admin`, solange `principal.bootstrap_admin` gesetzt **und** die Listen `BOOTSTRAP_ADMIN_*` die Person noch nennen). **`admin` kommt sonst nur über eine Zuordnung** (Standard: `events-admin→admin`); Bootstrap-Admins bleiben, solange die Settings sie nennen. `parse_group`/`grants_from_groups` bleiben als reine Funktionen für den Generator von `…/defaults`, für `seed_dev` und für die Test-Harness, **gehen aber nicht mehr in `resolve_principal` ein**.
5. `sync_principal_memberships(db, row) -> bool` (`app/modules/admin/membership_sync.py`, Muster `U backend/app/modules/admin/membership_sync.py`, PROVENANCE `U`): wünscht `{(organization_id, role)}` aus Schritt 2 und 3 (leer, wenn `row.active is False`), vergleicht mit den vorhandenen Zeilen von `row.id`, löscht überzählige, fügt fehlende ein, flush. Pro geänderter Zeile `audit_record(actor="oidc-sync", action=AuditAction.ROLE_CHANGE, target_type="membership", target_id=<organization_id>, data={principalId, role, change: "added"|"removed"})`; neues Audit-Enum `ROLE_CHANGE`. Kein Commit: der Aufrufer besitzt die Transaktion. Rückgabe `True`, wenn sich etwas änderte.
6. `sync_all_memberships(db) -> int`: derselbe Lauf für jede Person (aktuell wenige hundert; ein Statement für die Mappings, eines für die Organisationen).
7. **Hooks:** (a) am Ende von `auth.service.upsert_principal` nach `flush` (deckt Login `oidc_callback` **und** Revalidierung `renew_principal_session`, beide rufen die Funktion); (b) nach Anlegen, Ändern, Löschen einer Zuordnung; (c) nach Änderung von `organization.trusted`; (d) bei Deaktivierung einer Person (`active=false`, leert die Zeilen). Der Sync **liest keinen IdP**; er arbeitet auf dem Gruppen-Cache, den Login und Revalidierung füllen.
8. **Revalidierung (E24):** unverändert implementiert (`SESSION_REVALIDATE_HOURS=4`, `..._GRACE_HOURS=24`, nur Settings). M2 beweist sie: Abschnitt 6 Punkt 3. Entzug im IdP wirkt spätestens bei der ersten Anfrage nach Ablauf der 4 h, auf der der Refresh-Grant gelingt; ist der IdP dann nicht erreichbar, bleibt die Sitzung bis zum Ende der Gnadenfrist (24 h) und endet danach. Der Admin-Knopf (2.5) schließt die Lücke sofort.
9. **Weggelassener Claim:** Enthält das Refresh-ID-Token den `groups`-Claim gar nicht, bleiben die gecachten Gruppen (bestehendes Verhalten, bewusst vorsichtig, KARTE §5.2 Punkt 4). Ein **leeres** Array entzieht alles. Ob Keycloak und der Hochschul-Authentik bei Nutzern ohne Gruppe das leere Array senden, prüft Punkt 3 der Abnahme einmal gegen Keycloak und protokolliert es in `M2-ABNAHME.md`; ergibt sich "weggelassen", gilt Entscheidung D2.

Ein Zustandswechsel in der Auflösung (Mapping gelöscht, Trust entzogen) wirkt für **alle** Personen sofort bei der nächsten Anfrage, weil `resolve_principal` pro Request liest; `membership` zieht in derselben Transaktion nach.

## 5. Frontend

Besitz: `frontend/**`. Alles Angular standalone, OnPush, Signals, getrennte `.html`/`.scss`, i18n de (Deutsch, gegendert mit Doppelpunkt oder neutral), Komponenten aus `@stupa-makers/ui-kit` (`app-tabs`, `app-data-table`, `app-input`, `app-switch`, `app-dialog`, `app-button`, `app-card`, `app-toast`) und `@shared/ui` (`app-select`, `app-note`, `app-page-header`, `app-empty-state`); nie natives `<select>`, Status nur als farbiger Text (PLAN 15.0).

### 5.1 Navigation und Routen

- Neuer Eintrag `Verwaltung` in `NAV_ITEMS` (`key: 'admin'`, Pfad `/verwaltung`, `permissions: ['taxonomy.manage', 'venue.manage', 'admin.mappings']`, `place: 'main'`, Icon aus dem Kit). `NavService.visible` filtert über `AuthService.canAny`: sichtbar für `editor` und `admin`, für niemanden sonst. Das ist Bequemlichkeit; der Server entscheidet (jede Route 403).
- Routen in `feature-routes.ts` (Lazy, `authGuard` plus neuer `permissionGuard(...perms)` in `core/auth/`, Verweigerung leitet auf `/forbidden`): `verwaltung` (leitet auf den ersten erlaubten Tab), `verwaltung/kategorien` (`taxonomy.manage`), `verwaltung/orte` (`venue.manage`), `verwaltung/organisationen` (`taxonomy.manage`), `verwaltung/zuordnungen` (`admin.mappings`). Rahmen `AdminFrameComponent` mit `app-tabs` (Kategorien, Orte, Organisationen, Zuordnungen), Tabs nach Recht; M8 hängt Status (I25) und Audit (I26) an denselben Rahmen. `wide: true`.
- `/konto` bleibt in der Shell (`pages/account`).

### 5.2 I23 Taxonomie (`/verwaltung/kategorien|orte|organisationen`)

- Je Tab eine Tabelle (`app-data-table`) mit **Inline-Bearbeiten**: Klick auf eine Zeile macht sie bearbeitbar (`app-input`, `app-select`, `app-switch`), Knöpfe "Speichern" und "Abbrechen", oben "Hinzufügen" legt eine leere Zeile an. Slug ist beim Anlegen editierbar, danach schreibgeschützt. Fehler aus Problem+JSON erscheinen an den Feldern (`errors[].field`); 409 `slug_taken` zeigt "Slug schon vergeben."
- **Kategorien als Baum:** Zeilen nach Eltern geordnet und eingerückt (Daten aus `GET /api/admin/categories`, Baum im Client), Spalten Name, Art, Eltern (Auswahl ohne die Kategorie und ihre Nachfahren), Kurz, Farb-Token (Auswahl der sechs Tokens, Anzeige als Text, nie Hex), Pflichtfeld-Profil, aktiv. Hinweis (`app-note`): "Kategorien werden nicht gelöscht, nur deaktiviert."
- **Orte:** Name, Adresse, PLZ, Ort, Gebäude, Raum, öffentliche Präzision (`exact/building/hidden` als "genau/Gebäude/verborgen"), privat, Koordinate als zwei Zahlenfelder (Stufe C: Pin auf Karte), aktiv. Leere Adresse ist erlaubt (viele Bestandsorte).
- **Organisationen:** Name, Art, Kurz, Kategorie, Instagram-Konten (Komma-getrennt), `trusted`, aktiv. Der Schalter `trusted` ist **nur mit `admin.mappings`** bedienbar, sonst deaktiviert mit Grund; Umschalten öffnet einen Dialog: "Approver dieser Organisation dürfen eigene Events veröffentlichen."
- Leer: "Noch keine Einträge."

### 5.3 I24 Gruppen-Zuordnung (`/verwaltung/zuordnungen`)

- Tabelle `oidc_group · Rolle · Organisation · Personen`, "Zuordnung hinzufügen" (Gruppe als Text, Rolle als Auswahl mit deutschen Namen, Organisation als Auswahl, bei globaler Rolle leer und gesperrt, bei Org-Rolle Pflicht). Zeile bearbeiten (Rolle, Organisation) und löschen (Dialog, `danger`). Knopf "Standardzuordnungen anlegen" ruft `…/defaults` und meldet "3 neue Zuordnungen angelegt".
- Hinweis (`app-note`): "Gruppen kommen aus Authentik. Mitglieder werden nur dort gepflegt."
- Aufklappbare Vorschau "Wer bekommt was": die Personen der Gruppe (`GET /api/admin/principals?group=`: Name, E-Mail, letzter Login, Anzahl Sitzungen) mit dem Knopf **"Sitzungen widerrufen"** (`danger`, Bestätigungsdialog "Diese Person muss sich neu anmelden. Rechte ändern sich nur über Authentik.").
- Leer: "Noch keine Zuordnungen. Ohne Zuordnung sehen alle nur öffentliche Inhalte und eigene Vorschläge." Fehlertexte nach `code` aus 2.4; zusätzlich `duplicate_group`: "Diese Gruppe ist schon zugeordnet." und `last_admin_mapping`: "Die letzte Admin-Zuordnung bleibt, solange keine Bootstrap-Admins gesetzt sind."

### 5.4 I27, nur der Teil "Sitzungen widerrufen"

`/konto` bekommt einen Abschnitt "Sitzungen" mit "Andere Sitzungen widerrufen" (`danger`, Bestätigungsdialog), danach Toast "{n} Sitzungen beendet." (`POST /api/auth/sessions/revoke`). Zusätzlich zeigt das Konto Gruppen (lesend), Rollen und Organisationen mit Name statt Slug und, falls `trusted=false` und die Gruppe Approver verlangt hätte, nichts Besonderes (Rückstufung nur als `organizer`). Benachrichtigungen, Theme und Agenten (I27 vollständig) bleiben M4.

### 5.5 Dateien

`features/admin/{admin.routes.ts, admin-frame/, taxonomy/{categories,venues,organizations}/, mappings/, api/{taxonomy-api,mappings-api,sessions-api}.service.ts, api/admin.models.ts}`, `core/auth/permission.guard.ts`, `core/i18n/translations.admin.de.ts` (in `translations.ts` registriert), `features/account/session-section/`. Modelle nach Abschnitt 2.1 **von Hand**, nicht generiert. Kleine Komponenten, Kopf-Docstring je Datei, Kopien aus `U frontend/src/app/pages/admin/group-mappings/*` mit Herkunftsvermerk und `PROVENANCE.json`-Eintrag (Modus `U`).

## 6. Abnahme M2

### 6.1 Kriterium wörtlich (PLAN §16.1, Zeile M2, Spalte "Fertig wenn …")

> Matrix-Test Rolle × eigene/fremde/keine Org × Route grün; Partner-Testkonto bekommt 404 auf fremde Dossiers; Entfernen einer Gruppe im (Dev-)IdP entzieht den Zugriff spätestens nach der nächsten Revalidierung; neue Route ohne Rechte-Deklaration lässt CI scheitern

Lokale Lesart (wie M1: Keycloak statt Authentik): "Partner-Testkonto" ist `submitter-ekhg`; "nächste Revalidierung" heißt: `auth_session.revalidated_at` der Sitzung wird per SQL um 5 h zurückgesetzt (die Einstellung erlaubt mindestens 1 h), dann zählt die erste folgende Anfrage.

### 6.2 Prüfpunkte

1. **Matrix** (`tests/integration/events/test_rbac_matrix.py`, erweitert, plus `tests/integration/admin/test_rbac_matrix_admin.py`). Zeilen: `admin, editor, stupa, approver-stupa, approver-fsi, organizer-fsi, submitter-fsi, viewer-fsi, organizer-makers, submitter-ekhg, member, nobody`; Spalten: Dossier der **eigenen**, einer **fremden** Org, **ohne Org** (`member`/`nobody`) × {Lesen, Liste, Anlegen, Ändern, T01, T02, T04, Poster, Bild-Ausnahme} × alle M2-Routen. Erwartung exakt, kein `{403, 404}` mehr:
   - Lesen/Ändern/T-Übergang/Poster auf Dossier einer **fremden** Org durch jemanden, dessen Gate besteht (Org-Rolle mit dem Recht anderswo): **404**. Durch jemanden, dessen Gate nirgends besteht (`viewer`, `stupa`, `member`): Schreibrouten **403**, `GET` für `stupa` **200** (`event.read_all`), für `viewer`/`member` auf fremde Org **404**.
   - `stupa`: liest alles (200), Anlegen/Ändern/Übergänge/Poster **403**; `admin`: Bypass, alles erlaubt außer den harten Guards (`image_required` 422 bleibt); `member` und `nobody`: Liste `items=[]`, Lesen 404, Anlegen 403.
   - `submitter-ekhg` auf Dossier der Org `fsi`: 404 (Lesen, Ändern, Übergang, Poster, Guards); in der Liste fehlt es.
   - M2-Routen (jede Zeile ist ein Testfall): `/admin/organizations`, `/admin/categories` (Recht `taxonomy.manage`: `editor`, `admin` 200; alle anderen 403), `/admin/venues` (`venue.manage`: `editor`, `admin` 200, alle anderen 403), `/admin/group-mappings`, `/admin/principals`, `…/defaults`, `trusted` setzen (nur `admin` 200, `editor` 403), `/admin/principals/{id}/sessions/revoke` (nur `admin`), `/auth/sessions/revoke` (jede Session 200, ohne Session 401), `GET /organizations|categories|venues` (jede Session 200, ohne Session 401).
2. **Sichtbarkeit** `test_visibility` (Dossier-Ebene aus §5.4): eigene Org ja, andere Org 404, `stupa` lesen, `editor` ja, `member` nur eigener Vorschlag (Vorschläge kommen mit M3: die Testzeile steht als `xfail(strict=True, reason="M3 Vorschläge")`, aufgeführt in der Abnahme). Anhang-Ebene (`team|org|shared`, Angebote, Verträge) ist **M4**.
3. **Entzug über die Revalidierung gegen Keycloak** (`backend/scripts/m2_acceptance.py`, echter OIDC-Flow wie `m1_acceptance.py`): (a) `organizer-fsi` meldet sich an, `GET /api/events` zeigt ein Dossier der Org `fsi`, `/auth/me` nennt `fsi/organizer`; (b) das Skript entfernt die Person über die Keycloak-Admin-API (`admin/admin`, Realm `stupa-events`) aus `events-fsi-organizer`; (c) vor Ablauf der Frist: Zugriff besteht noch; (d) `UPDATE auth_session SET revalidated_at = now() - interval '5 hours'`; (e) die nächste Anfrage liefert `/auth/me` ohne `fsi` und `GET /api/events/{id}` **404**; (f) Gruppe zurück, neue Anmeldung, Zugriff wieder da. Zusatz: Nutzer, der **alle** Gruppen verliert (`submitter-ekhg` aus `events-ekhg-submitter`): Verhalten des `groups`-Claims im Refresh-Token wird beobachtet und in `M2-ABNAHME.md` festgehalten (Abschnitt 4 Punkt 9, D2). Dazu Unit-Tests `test_session_renewal` für beide Fälle (Claim leer/fehlend).
4. **Routen-Inventur** (`tests/unit/test_route_authz_inventory.py`, Abschnitt 7): neue Route ohne Eintrag lässt `be-unit` scheitern; ein Meta-Test beweist, dass die Prüfung eine absichtlich ungesicherte Hilfsroute erkennt.
5. **`membership_sync`:** `tests/unit/admin/test_membership_sync.py` (Hinzufügen, Entfernen, Rückstufung `approver` bei `untrusted`, zweimal laufen = 0 Änderungen, `active=false` leert, `events-system:` ohne Wirkung) und `tests/integration/admin/test_membership_hooks.py` (Login-Callback, Revalidierung, Mapping-Änderung, `trusted`-Wechsel schreiben `membership`).
6. **Admin-APIs:** `test_group_mapping_api` (alle Validierungscodes aus 2.4, Duplikat, Aussperrschutz, `defaults` idempotent und ohne `approver` für nicht vertraute Orgs), `test_taxonomy_admin_api` (Anlegen, Patch, Slug-Wechsel 422, Zyklus, Koordinatenpaar, `trusted` nur `admin.mappings`, kein `DELETE`-Route), `test_sessions_revoke` (eigene: die laufende bleibt, die anderen enden; Admin: alle enden, nächste Anfrage 401; Audit-Eintrag ohne E-Mail).
7. **Referenzdaten:** `test_reference_data` (27 Kategorien, 13 Organisationen, nur `stupa` trusted, 6 Kinder unter `fachschaft`, die fünf Slug-Umbenennungen, `tec.legacy_wp_ids = {}`) und `test_venue_reference` (genau 44 Orte, eindeutige Slugs, `legacy_wp_id` eindeutig, alle `lat`/`lon` NULL, Adressen nur aus Abschnitt 3.3, `normalize_room_key`-Property). `test_migrations`: `alembic heads` genau ein Head `0003_roles_taxonomy`; frische DB und M1-Upgrade ergeben dieselben Zeilen.
8. **Coverage:** `scripts/coverage_critical.py` (neu, PLAN 12.1) prüft 100 % Branch für `auth` (ohne die Dateien, die M1 unverändert kopiert hat und die Mutationen unter 100 % tragen: Liste in der Datei, mit Begründung je Eintrag), `audit` und `pipeline`/`publicapi` (weiter); Gesamt-Gate bleibt 90 % (Anhebung auf 97 % bis M5). `files` und `media` werden erst gehoben, wenn M4 sie ändert (Abweichung 10.2).
9. **Frontend:** Jest-Specs je Komponente und Service (inkl. axe-Test wie M1), `permissionGuard`-Test, Nav-Test (`editor`/`admin` sehen "Verwaltung", `organizer` nicht). **Playwright `frontend/e2e/m2.spec.ts`** (Browser aus nixpkgs wie M1): (1) `admin` öffnet `/verwaltung/zuordnungen`, legt eine Zuordnung an und sieht den Fehler `reserved_group_prefix`; (2) `editor` sieht Kategorien/Orte/Organisationen, aber keinen Tab Zuordnungen, der Schalter `trusted` ist gesperrt; (3) `organizer-fsi` sieht keine Navigation "Verwaltung", `/verwaltung/orte` führt auf "Keine Berechtigung"; (4) `submitter-ekhg` öffnet die URL eines FSI-Dossiers und sieht die 404-Seite; (5) `organizer-fsi` klickt "Andere Sitzungen widerrufen" in einer zweiten Sitzung und die zweite Browser-Sitzung wird anonym.
10. **Gates wie M1:** `ruff check`/`format --check`, `basedpyright` 0 Fehler, `pytest -m 'not integration and not e2e and not live'`, `pytest -m integration`, `PROVENANCE_STRICT=1` (`test_provenance`), `alembic heads`, `npm run lint`, `npm run typecheck`, `npm test`, `npm run build`, `deploy/compose-lint.sh`, `deploy/smoke.sh`, Playwright `m1.spec.ts` und `m2.spec.ts`, `gitleaks detect`.

### 6.3 M1-Reste (gehören zur Abnahme M2)

| Rest | Maßnahme | Prüfung |
|---|---|---|
| **Doppelter CSP-Header auf `/api`** (L18) | In `deploy/web/api-proxy.conf` (von allen `/api`-, `/ics`-, `/e/`-, `/k/`-Locations eingebunden) `proxy_hide_header` für `Content-Security-Policy`, `Permissions-Policy`, `Referrer-Policy`, `X-Content-Type-Options`, `X-Frame-Options`. nginx liefert so genau einen Satz aus `security-headers.conf` (jede Location bindet ihn ohnehin ein, `compose-lint.sh` bleibt grün); die API-Header bleiben als Schutz, wenn jemand sie ohne nginx erreicht. Besitzer: Backend-Builder | `deploy/smoke.sh` zählt je Pfad, dass jeder dieser fünf Header **genau einmal** vorkommt (heute: nur "mindestens eine CSP"); `GET /api/auth/me` liefert nach nginx `Referrer-Policy: strict-origin-when-cross-origin` |
| **5 `tsc`-Fehler** (L19) | `truncated.directive.spec.ts(64)`: Typ des Mocks; `select.component.spec.ts(518,519)`: `delete` auf optionalem Feld (Typ `Partial` oder `Reflect.deleteProperty`); `testing/a11y.ts(14,39)`: `AxeResults` aus `axe-core` importieren und Rückgabetyp von `toHaveNoViolations` anpassen. Dazu `npm run typecheck` = `tsc -p tsconfig.app.json --noEmit && tsc -p tsconfig.spec.json --noEmit`, damit CI die Specs mitprüft. Besitzer: Frontend-Builder | `npm run typecheck` ohne Fehler |
| `GET /api/organizations?creatable=true`, `GET /api/categories` | **existieren** (1.1); M2 ergänzt `?tree=true`, `VenueRef`-Liste und die Admin-Routen | `test_organization_list`, `test_category_list` angepasst |
| MinIO-Service-Konto (M1-Abnahme "Offen") | **nicht in M2** (Betrieb, M8/Deploy), bleibt offen | |

Die Abnahme schreibt `docs/M2-ABNAHME.md` im Format von `M1-ABNAHME.md` (Ergebnistabelle, Befehle, gekürzte Ausgabe, "Offen").

## 7. Routen-Inventur (`tests/unit/test_route_authz_inventory.py`, erweitert)

PLAN 5.5. Zusätzlich zu den vier bestehenden Tests:

1. **`EXPECTED_GATE_PERMS` wird vollständig.** Jede nicht-öffentliche Route steht mit der Menge ihrer Gate-Rechte in `ROUTE_PERMS: dict[(method, path), frozenset[str]]`. Der Test `test_every_route_has_an_expected_permission_set` vergleicht die Menge der Routen der App mit den Schlüsseln (beide Richtungen) und die Rechte je Route. Eine neue Route, die niemand einträgt, scheitert; eine entfernte Route mit Eintrag scheitert ebenfalls.
2. **Gate ohne Recht nur auf der Liste** `SESSION_ONLY_ALLOWLIST = {GET /api/auth/me, POST /api/auth/sessions/revoke}`. Jede andere Route mit leerem `authz_perms` scheitert (heute besteht `require_principal()` ohne Argument die Inventur, obwohl es nichts prüft). Lesen für die Allgemeinheit schreibt sich `require_principal("library.read")`.
3. **Meta-Test:** der Test baut eine kleine `FastAPI`-App mit einer ungesicherten Route und einer Route mit leerem Gate und beweist, dass die Prüffunktion beide meldet.
4. **Admin-Routen** `/api/admin/*` (außer `…/audit`, das dort schon steht) erscheinen mit ihren Rechten: `taxonomy.manage` (organizations, categories), `venue.manage` (venues), `admin.mappings` (group-mappings, principals), `admin.sessions.revoke` (principals/{id}/sessions/revoke); `trusted` prüft die Route zusätzlich im Handler mit `principal.has("admin.mappings")` (nie über `principal.roles`).
5. Keine Public-Route mit Session (bestehend) bleibt; `PUBLIC_ALLOWLIST` bekommt keinen neuen Eintrag.

## 8. Verzeichnisbesitz

Zwei Builder, beide schreiben nur in ihren Bereich. Konflikte löst die Orchestrierung. Kopien aus Upstream mit Kopf `Copied from STUPA-Workflow@93c33d6 <pfad>` und Eintrag in `PROVENANCE.json` (Modus `U`); nichts wird gebündelt oder übernommen, ohne dass der Builder die Quelle gelesen hat.

| Builder | Besitzt | Aufgaben |
|---|---|---|
| **backend** | `backend/**` | `0003_roles_taxonomy`; `orgs/`, `taxonomy/` (Referenz, Venue-Modell, Schemas, Lese-Router `venues`); neues Modul `app/modules/admin/` (`membership_sync.py`, `mappings.py`, `taxonomy_router.py`, `mappings_router.py`, `principals_router.py`, `schemas.py`); `auth/` (`rbac.effective_grants`, `upsert_principal`-Hook, `sessions.end_other_principal_sessions`, `router` für `/auth/sessions/revoke` und `/auth/me`); `shared/permissions.py` (`venue.manage` für `admin`, Generator der Standardzuordnungen); `audit/actions.py` (`ROLE_CHANGE`); `publicapi` (`slug`); `api_routers.py`; `tests/**` inkl. Harness (legt die Mappings der Testgruppen an), `scripts/{seed_dev.py,m1_acceptance.py,m2_acceptance.py,coverage_critical.py}`, `seeds/dev_events.yaml` |
| **backend** (außerhalb `backend/`, nur diese Dateien) | `deploy/web/api-proxy.conf` (Fix L18), `deploy/smoke.sh`, `deploy/db/roles.sql`, `deploy/keycloak/stupa-events-realm.json`, `docs/M2-ABNAHME.md`, `.claude/skills/be-{auth,events}/SKILL.md`, `CLAUDE.md`, `README.md` | Header genau einmal prüfen; `DELETE` für `group_mapping` und `membership`; Nutzer aus Abschnitt 2.8; Skill `be-auth` korrigieren ("Organisationen kommen mit DB-Abfrage"); neue Nutzer und Routen in README |
| **frontend** | `frontend/**` | alles aus Abschnitt 5, Abschnitt 6.3 (tsc), `frontend/e2e/m2.spec.ts`, `.claude/skills/frontend/SKILL.md` |

Schnittstellen: Typen aus Abschnitt 2.1 sind der gemeinsame Vertrag; der Frontend-Builder baut gegen `?demo=`-freie echte API (Dev-Stack) und gegen gemockte `HttpTestingController`-Antworten. Der Backend-Builder liefert zuerst Abschnitt 2.2 bis 2.6 samt Realm-Nutzern; danach arbeiten beide parallel. Keine Datei in `.github/**` ändert sich (CI ruft `npm run typecheck` und die bestehenden Jobs auf).

## 9. Entscheidungen für Luis (Vorschläge, nicht belegt)

Der Kontrakt arbeitet mit der **fett** markierten Voreinstellung, bis Luis anders entscheidet.

| # | Frage | Voreinstellung | Alternative / Folge |
|---|---|---|---|
| D1 | **Rechte nur aus `group_mapping`** (PLAN 5.6, M1-Abweichung 7) oder weiter zusätzlich nach Namensschema? | **nur Mapping**; `parse_group` bleibt Generator für `…/defaults` | Schema + Mapping wie M1: weniger Pflege (52 Zeilen), aber Gruppennamen bleiben im Code, Umbenennung in Authentik bricht still |
| D2 | Bleibt ein Recht erhalten, wenn das Refresh-Token den `groups`-Claim **weglässt**? | **ja** (vorsichtig, KARTE §5.2); Admin-Knopf als Rückfall | Weggelassen = leer, wenn der Selbsttest (E38) belegt, dass der IdP `groups` immer sendet (M8, Statusseite) |
| D3 | Kategorie-Slugs an den Altbestand angleichen (L8)? | **ja**, fünf Umbenennungen in `0003` | M1-Slugs behalten und die Abweichung in Abschnitt 10 nachführen; WordPress/Astro mappen über `legacy_wp_id` |
| D4 | `event.venue_id` und Orts-Auswahl im Dossier in M2? | **nein, M3** (Formular-Umbau, View, Feed) | M2 würde View und Feed-Schema anfassen |
| D5 | Aussperrschutz `last_admin_mapping` | **an** (nur wenn keine Bootstrap-Admins gesetzt sind) | weglassen: Admin kann sich per UI aussperren, Bootstrap-Liste rettet |
| D6 | "Eigene Sitzungen widerrufen" beendet die laufende Sitzung nicht | **laufende bleibt** | alle inklusive laufender, Antwort mit `logoutUrl` |
| D7 | `trusted` nur über das Recht `admin.mappings` (kein neues Recht erfunden) | **ja** | eigenes Recht `org.trust` im Katalog |
| D8 | `stupa` bleibt `trusted` (M1-Seed) trotz E05 "Start: keine Organisation trusted" | **ja**, sonst gibt es in der Dev-Abnahme keinen vertrauten Approver | `trusted` für alle `false`, der Test `approver-stupa` legt es selbst an |

## 10. Abweichungen vom PLAN und von M1 (zur Nachführung durch Luis)

1. **`group_mapping` als einzige Quelle** (D1) setzt die M1-Abweichung 7 um; PLAN 5.6 bleibt, der Vorschlag der Gruppennamen wandert aus dem Code in `…/defaults`.
2. **Coverage:** `coverage_critical.py` gilt in M2 für `auth`, `audit`, `pipeline`, `publicapi`; `files` und `media` folgen mit M4 (M1-Abweichung 5 verschoben, weil beide in M2 unverändert bleiben).
3. **`membership`-Zeilen sind keine Entscheidungsgrundlage**, nur Projektion (PLAN 3.3 "nur der Sync schreibt" bleibt; die Auflösung liest `group_mapping` direkt, PLAN 5.1 "nie über `principal.roles`").
4. **Kein `principal.last_revalidated_at`**; der Zeitpunkt steht an `auth_session`.
5. **Kategorien: 27 statt "22 + 3"**: KARTE §9 und PLAN 3.3 führen `hochschule` und `ekhg` zusätzlich zu LS, NXT, ESB; die Aufgabenformulierung "3 neue" wird als "5 neue" gelesen.
6. **Organisationen: 13 statt 12**: `praesidium` bleibt (PLAN 3.3, KARTE §2.6).
7. **Adressen der 44 Orte sind lückenhaft** (Quelle nennt nur etwa elf); GPS und `public_precision` pflegt Stufe C (C2).
8. **Feed:** `organization.slug` ist neu; PLAN 8.2 (`organizers [{slug, name, url}]`, `orgShort`) und der M1-Feed weichen weiter voneinander ab (M1-Abweichung 1).
9. **Eigene Sitzungen:** PLAN 5.1 kennt nur "Admin-Knopf je Person" (E24); die Selbstbedienung in I27 ("Sitzungen widerrufen", Aufgabe M2) ist die einzige Ergänzung ohne PLAN-Text, abgesichert durch D6.
10. **Venue-Slugs bereinigen Tippfehler, Kategorie-Slugs nicht:** Kategorien folgen dem Altbestand (D3, KARTE §9 "bestehende Slugs bleiben"), Orte nicht (`kinosaal-9-113` wird `kinosaal-9-133`, `maschienenhalle-geb-1` wird `maschinenhalle-geb-1`, `rase-…` wird `rasen-…`). Die Archiv-URLs `/veranstaltungsort/<slug>/` weichen damit vom Live-System ab; WordPress/Astro mappen über `legacy_wp_id`. Offen für Luis: Live-Slugs behalten und die saubere Form nur in `name` führen.
11. **`0003` ist nicht rein additiv:** die Migration benennt fünf Kategorie-Slugs um (D3) und ändert so Feed-Filter wie `?category=lan-party`. Umbenennungen und Korrektur von `tec` stehen eingebettet in der Migration; die Ortsdaten sind per Hash-Test festgelegt.
