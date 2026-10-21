# M5b-Kontrakt: Rückbau zum Event-Dossier

Stand 2026-10-21, auf `feat/m5-archiv` (M1 bis M5 committed, HEAD `aebf331`); der Branch `feat/m5b-vereinfachung` entsteht im Integrationsschritt. Verbindlich: `stupa-events-plan/ENTSCHEIDUNGEN.md`, Abschnitt "Kurskorrektur von Luis (2026-10-21)". Sie überschreibt PLAN §4 (Pipeline), §15.1 I02, I03, I13, I14, I15 und alle Vier-Augen- und Feldklassen-Regeln. Alles andere aus `M1` bis `M5-KONTRAKT.md` gilt weiter, soweit unten nichts anderes steht. Maßstab von Luis: "möglichst einfach zu jedem Event die Doku"; die Pipeline ist Sache des Workflow-Tools. Quelle der Inventur: der Arbeitsbaum am genannten Stand (gelesen, nicht gelaufen). Was nicht gelesen wurde, steht als "Builder prüft".

Regeln wie bisher: Upstream-Konventionen, camelCase mit `extra=forbid`, Problem+JSON, tz-aware, Rechte nur über `Principal.has(perm, org_id)`, 404-Regel für unlesbare Dossiers, Angular standalone mit signals und ui-kit, i18n de, Jest, Playwright, `PROVENANCE.json`, kleine Dateien mit Kopf-Docstring, keine Trennkommentare. Code und Commits Englisch, UI Deutsch gegendert. Kein Eingriff in Live-Systeme. **Löschen statt Verstecken**: toter Code, Tests, i18n-Schlüssel, Routen, Spalten und Skripte, die der Rückbau überflüssig macht, werden entfernt, nicht auskommentiert und nicht hinter Flags gelassen.

## 1. Zielbild

1. Die Plattform ist ein Event-Dossier: zu jedem Event gibt es eine Seite, auf der die Doku (Anleitung, Anhänge, Checkliste, Mailvorlagen, Angebote, "So lief es") an einem Ort liegt.
2. Ein Event hat drei Zustände: Entwurf, Veröffentlicht, Archiv; dazu das Kennzeichen "abgesagt" (oder "verschoben") für den öffentlichen Status.
3. Die Organisation veröffentlicht ihre Events selbst; die Redaktion darf alles veröffentlichen, zurückziehen, archivieren und wiederherstellen.
4. Es gibt keine Freigabe, kein Vier-Augen-Prinzip, keine Feldklassen und keine Übergangs-Dialoge; die Pipeline gehört dem Workflow-Tool.
5. Das Bild ist keine Pflicht, aber der erste Blick: großer Poster-Slot oben im Dossier, Thumbnail oder Platzhalter in Liste und Kalender, ein Hinweis "Ohne Bild nicht bewerbbar" solange es fehlt.
6. Ein Event lässt sich mit drei Angaben veröffentlichen (Titel, Beginn, Organisation); alles andere erscheint als Hinweis, nie als Sperre.
7. Einstieg ist die Event-Liste mit Filterchips und einem Umschalter auf den Kalender; "Neu aus Vorlage" steht gleichwertig neben "Neues Event".
8. Formate, Bibliothek und die Suche im Archiv (M5) bleiben unverändert in Funktion und Rechten.
9. Der öffentliche Feed und die ICS-Kalender bleiben im Schema gleich; sie liefern veröffentlichte und archivierte Events, ein fehlendes Bild ergibt `image: null`.
10. Zwölf Stunden nach dem Ende archiviert der Worker ein veröffentlichtes Event von selbst; das Archiv bleibt für die Doku beschreibbar (Abschnitt 2.4), damit "So lief es" auch danach ausgefüllt werden kann.

## 2. Zustandsmodell

### 2.1 Zustände und Kennzeichen

`event.state` ist `draft | published | archived` (CHECK `ck_event_state`, Server-Default `draft`, Enum `EventState` in `events/states.py`). `public_status` (`scheduled | cancelled | postponed`) und `public_reason_code` (`none, room, speaker, illness, registration, weather, other`) bleiben als Spalten und CHECKs unverändert; das Kennzeichen "abgesagt" ist `public_status = 'cancelled'` mit dem Grund-Enum, kein neuer Spaltenname. Feed und ICS lesen weiter `public_status`. `public_status` ist nur bei `published` änderbar; ein archiviertes Event behält den letzten Wert.

### 2.2 Übergänge und Rechte

Jeder Übergang ist eine eigene Route (Abschnitt 7), schreibt eine Zeile `event_status_event` (`transition_id` ist das Aktionswort `publish`, `unpublish`, `archive`, `restore`, `cancel`, `postpone`, `reinstate`; der Worker schreibt `archive` mit `actor_type = 'system'`) und eine `event_revision`, und führt `invalidate_feed_cache` aus (Muster `pipeline/actions.py`, das Modul zieht nach 5.1 um).

| Aktion | Von | Nach | Recht | Wirkung |
|---|---|---|---|---|
| `publish` | `draft` | `published` | `event.publish` in der Organisation des Events; bei `publish_requires_editor = true` nur Redaktion | `slug` setzen, falls leer (`slugs.base_slug`), `public_seq + 1`, Ableitungen anstoßen (`ensure_derivatives`) |
| `unpublish` | `published` | `draft` | `event.publish` in der Organisation | `public_seq + 1`; `slug` bleibt (stabile Adresse) |
| `archive` | `draft`, `published` | `archived` | `event.publish` in der Organisation; Worker 12 h nach `ends_at` | `public_seq + 1` falls vorher `published` |
| `restore` | `archived` | `draft` | `event.restore` (Redaktion) | kehrt als Entwurf zurück und verlässt Feed und ICS bis zur nächsten Veröffentlichung |
| `cancel` | `published` | `published` | `event.cancel` in der Organisation | `public_status = cancelled`, Grund-Enum, optional Text; `public_seq + 1` |
| `postpone` | `published` | `published` | `event.cancel` | `public_status = postponed`, optional neue Zeit; `public_seq + 1` |
| `reinstate` | `published` | `published` | `event.cancel` | `public_status = scheduled`, Grund geleert; `public_seq + 1` |

Voraussetzung von `publish` ist nur `title`, `starts_at` und `organization_id` (bei `draft` gibt es Altzeilen ohne Organisation, 2.5). Fehlt etwas: 422 `publish_incomplete` mit `reasons[]` (Feldname je Eintrag). Sonst blockiert nichts: kein Bild, keine Kategorie, kein Ort, keine Checkliste. Fehlerfälle wie bisher: unlesbar 404, kein Recht 403, falscher Zustand 409 `invalid_state`, veraltete `rev` 412/409 über `If-Match` wie in `events/conflict.py`.

`publish_requires_editor` ist eine Einstellung in `app/settings.py` (Umgebungsvariable `PUBLISH_REQUIRES_EDITOR`, Standard `false`) und ersetzt `editor_four_eyes`. `deploy/*.env*`, `.env.example` und `tests/unit/test_env_example_settings_parity.py` ziehen nach. Der Server entscheidet; `allowedActions` im Event (Abschnitt 7) trägt das Ergebnis zum Client, der Client rechnet nichts nach.

### 2.3 Bearbeiten je Zustand

Eckdatenfelder (alles aus `DraftFields`) sind in `draft` mit `event.edit` änderbar (Submitter nur eigene), in `published` mit `event.publish` (Organizer der Organisation, Redaktion), in `archived` nicht (erst `restore`). Es gibt keine `editableFields`-Berechnung nach Feldklassen mehr; `editableFields` im Event bleibt als Liste und ist je Zustand und Recht entweder alle Felder oder leer. Änderungen an `published` rufen weiter `public_seq + 1` (wenn ein öffentlich sichtbares Feld sich ändert; Builder übernimmt die Feldliste aus `pipeline/fieldclass.py` `bump_public_seq`, bevor die Datei fällt) und die Feed-Invalidierung aus. `autosave` (`editor_draft`) und die Versionskonflikt-Logik (`events/conflict.py`, `If-Match`) bleiben unverändert.

### 2.4 Das Archiv bleibt für die Doku offen (Annahme, Luis bestätigt)

Der Worker archiviert 12 h nach dem Ende. "So lief es" und Anleitungsprüfung entstehen aber nach dem Event. Darum fällt `dossier/rules.py` `CLOSED_STATES`/`ensure_open` für `archived` weg (heute 409 `dossier_closed` für `archived` und `withdrawn`). Im Archiv bleiben schreibbar: Dokumente (Anleitung, Notiz, Rückblick, Mailvorlagen), Anhänge, Checkliste, Kommentare, Angebote, `outcome`, `facts`-unabhängig; gesperrt bleiben nur die Eckdaten (2.3), Poster-Austausch und `public_status`. Rechte wie bisher je Aktion (`event.edit`, `dossier.attach`, `comment.write`; Submitter nur eigene).

### 2.5 Datenmigration `0007_event_dossier` (additiv und abbauend)

Revision `0007_event_dossier`, `down_revision = "0006_archive_feed"`, Muster `0006` (Datenschritte zuerst, dann Constraints, dann Löschen). Keine Produktivdaten (Pilot nicht gestartet, M5-ABNAHME "Offen"); trotzdem verlustarm für die Dev-DB. Reihenfolge:

1. **Zustände** (`UPDATE event`, je Zeile eine Zeile `event_status_event` mit `transition_id = 'migration-0007'`, `actor_id = 'system:migration-0007'`, `actor_type = 'system'`, `from_state`, `to_state`; `rev` bleibt):
   `idea, planning, in_review, withdrawn` -> `draft`; `approved` -> `draft` (auch bei erreichtem `publish_at`, weil der Worker es sonst schon veröffentlicht hätte; die Zahl wird im Alembic-Log ausgegeben); `live` -> `published`; `followup` -> `archived`; `archived` bleibt. Das ergibt acht Altzustände auf drei neue.
2. **Rollen**: `group_mapping.role` und `membership.role` `approver` -> `organizer` (bei `membership` zuerst die `approver`-Zeilen löschen, zu denen es für dieselbe Person und Organisation schon `organizer` gibt, dann umbenennen, wegen des Schlüssels `(principal_id, organization_id, role)`); danach die CHECKs `ck_membership_role` und die Rollenliste der Gruppen-Zuordnung (`0002` `_ROLES`) ohne `approver`.
3. **Benachrichtigungen**: Zeilen mit entfernten Kinds aus `notification` und `notification_pref` löschen (Posteingang ist flüchtig, `gc_notifications` räumt ohnehin), CHECKs `kind` auf `comment_added, published, cancelled, checklist_due` (Abschnitt 6).
4. **Constraints**: `ck_event_state` auf die drei Zustände; `ck_event_organization` auf `state = 'draft' OR organization_id IS NOT NULL` (Altzeilen ohne Organisation sind nur `draft`); `ck_event_status_event_to_state` bleibt eine Obermenge (drei neue **und** die acht alten Werte), weil `event_status_event` und `event_revision` append-only sind und die Verlaufszeilen unverändert bleiben (Trigger `append_only_guard`); der Verlauf zeigt alte Zustände als Text. Neu: `ck_event_tzid` `tzid = 'Europe/Berlin'` (M5-Review).
5. **View**: `public_event_v` neu mit `WHERE (e.state = 'published' OR (e.state = 'archived' AND e.published_at IS NOT NULL)) AND e.slug IS NOT NULL` (`published_at`: gesetzt bei `publish`, gelöscht bei `unpublish` und `restore`), ohne den `exception_ok`-Zweig (`a.id IS NOT NULL OR exception_ok(...)` fällt ganz weg); die Poster-Spalten bleiben `LEFT JOIN`, ohne Poster sind sie NULL und der Feed liefert `image: null` (`publicapi/schemas.py` hat `image: PublicImage | None`, `feed-v2.json` erlaubt `null`). Die View-Spalten bleiben gleich, `allowlist.py` ändert sich nicht; `GRANT SELECT` für `events_public` bleibt.
6. **`attachment_poster_ok(a)` entschärfen** (Funktion neu, die View nutzt sie im Join): `kind = 'poster' AND scan_status = 'clean' AND retired_at IS NULL AND derivatives ?& {thumb_400, card_1200, og_1200x630}`. Alt-Text, Credit und `rights_basis <> 'unknown'` sind nicht mehr Bedingung für das Erscheinen im Feed (sie werden Hinweise, 3.2). Die Einwilligungsregel `persons_depicted` ohne `consent_note` bleibt Bedingung (Datenschutz, nicht Pipeline), solange Luis das nicht anders entscheidet (13.1 O1).
7. **Löschen** (Reihenfolge: Trigger, Funktionen, Spalten): Trigger `trg_event_enforce_publish_image` und `trg_attachment_keep_published_poster`, Funktionen `enforce_publish_image()`, `keep_published_poster()`, `exception_ok(jsonb)`; Spalten `event.submitted_by`, `event.approved_by`, `event.image_exception`, `event.publish_at`, `event.published_rev`, `event.text_reviewed_rev`, `event.flyer_checked_at`; `event_status_event.four_eyes`, `event_status_event.submitted_by` samt `ck_event_status_event_four_eyes`; `event_revision.field_class` samt CHECK (das Revisions-API verliert den Filter `fieldClass`); `organization.trusted`. `end_estimated`, `howto_verified_at/by`, `outcome`, `facts`, `location_*`, `format_id`, `derived_from_id` bleiben. Der Index `ix_event_state` bleibt.
8. `downgrade()` stellt Spalten (nullable) und Zustände nicht wieder her; die Migration ist einseitig und sagt es im Docstring (wie `0006`).

Die Tabellen `task`-ähnlicher Art gibt es nicht (das Modul `tasks` ist eine Abfrage, keine Tabelle); `event_draft`/`editor_draft` bleibt.

## 3. Bild und Hinweise

### 3.1 Bild: optional, aber vorn

- **Poster-Slot** oben im Dossier, groß (volle Spaltenbreite, Seitenverhältnis des `card_1200`), Drag & Drop und Dateiwahl, Ersetzen und Entfernen; baut auf `shared/ui/poster-upload` und `shared/ui/file-drop-zone` auf (der heutige Einbau in `dossier-detail.component.*`). Ohne Bild zeigt der Slot eine Fläche mit Text "Ohne Bild nicht bewerbbar" und einer Schaltfläche "Bild hochladen".
- **Liste und Kalender**: Thumbnail (`thumb_400`) oder Platzhalter. `EventCard.hasPoster` (bool) bleibt; neu `EventCard.posterThumbUrl` ist nicht nötig, solange der Client die Datei über `GET /api/events/{id}/poster/file?variant=thumb400` holt (Route besteht, `dossier/router.py`); Builder prüft, ob das für 50 Karten pro Seite reicht, sonst ein zusätzliches Feld `posterSha` für den Cache-Schlüssel.
- **Hinweisbanner** im Dossier: bei `published` ohne Poster "Ohne Bild nicht bewerbbar" (Hinweis `no_poster`, 3.2), auch in der Listenkarte als kleines Symbol.
- **Feed** liefert `image: null`; die öffentliche Seite (Stufe B) zeigt den Platzhalter. `feed-v2.json` und `allowlist.py` ändern sich nicht.
- Alt-Text und Credit bleiben im Poster-Formular (`attachment`-Metadaten), empfohlen, nicht erzwungen. `image_exception` und alles drum herum entfällt.

### 3.2 `missing_info(event)`: reine Funktion statt Guard-System

Neue Datei `backend/app/modules/events/hints.py` mit `missing_info(snapshot: HintInput) -> list[Hint]`, rein (keine Datenbank; die Eingabe baut ein Lader mit wenigen gruppierten Abfragen, Muster `dossier/guard_data.py`, das danach schrumpft oder in `events/` aufgeht). `Hint` ist `{code, severity, field}` mit `severity` `info | warn`; der Text kommt aus i18n (`hints.<code>`), nicht vom Server. Codes:

| Code | Wann | severity |
|---|---|---|
| `no_poster` | kein gültiges Poster (Anzeige "Ohne Bild nicht bewerbbar") | `warn` bei `published`, sonst `info` |
| `poster_alt_missing`, `poster_credit_missing` | Poster ohne Alt-Text / Credit | `info` |
| `poster_consent_missing` | `persons_depicted` ohne Einwilligungsnotiz (Poster erscheint dann nicht im Feed) | `warn` |
| `poster_not_ready` | Poster `pending`, `infected` oder ohne Ableitungen | `warn` |
| `no_organization` | Altentwurf ohne Organisation (die Redaktion weist zu, sonst nicht veröffentlichbar) | `warn` |
| `no_summary`, `no_category` | leer | `info` |
| `no_venue` | weder `venue_id` noch `venue_text` | `info` |
| `location_unconfirmed` | freier `venue_text` ohne Bestätigung (steht im Feed nicht, M5 2.2) | `warn` |
| `facts_incomplete` | Pflichtangaben des Profils fehlen (heute `facts.error_for`, z. B. `ageLimit` bei Party) | `info` |
| `howto_missing` | keine Anleitung am Event und kein Format mit Anleitung | `info` |
| `outcome_open` | Event vorbei, `outcome` leer und nicht verzichtet | `info` |

Die Funktion kennt keine Blocker. Einziger harter Fehler beim Veröffentlichen ist `publish_incomplete` (2.2); die Prüfung steht in `events/publish.py` neben dem Übergang, nicht in `hints.py`.

## 4. Rechte

### 4.1 Rollen

Organisationsrollen `viewer`, `submitter`, `organizer`; globale Rollen `editor`, `stupa`, `member`, `admin`. **`approver` entfällt** samt `organization.trusted`, der Herabstufung in `auth/rbac.py` (`effective_grants`, `grants_from`, `MappingRow` ohne `trusted`), `default_mappings` (kein `trusted`-Parameter), Gruppenname `events-<org>-approver` in `shared/permissions.py` `_ORG_GROUP`, `admin/organizations_router.py` (Zweig `trusted`, Prüfung `admin.mappings`), `admin/schemas.py`, `auth/schemas.py` und `/auth/me` (`organizations[].trusted`), `taxonomy/reference.py` (`trusted=True` für `stupa`), `admin/membership_sync.py` (Neuabgleich bei `trusted`-Änderung), und im Frontend `core/api/models.ts`, `features/admin/taxonomy/organizations/*`, `admin-errors.ts`, `admin.models.ts`, `translations.admin.de.ts`.

### 4.2 Berechtigungskatalog (`shared/permissions.py`)

Entfernt: `event.approve`, `event.image_exception`, `event.edit_critical_live`, `event.assign_org`, `event.submit`. Neu: `event.publish` (ersetzt `event.submit` und `event.approve`). Bleiben: `event.read_all`, `event.create`, `event.edit`, `event.cancel`, `event.restore`, `dossier.attach`, `dossier.read_restricted`, `comment.write`, `library.read`, `library.manage`, `format.manage`, `series.manage`, `offer.manage`, `import.review`, `import.manage`, `taxonomy.manage`, `venue.manage`, `audit.read`, `audit.verify`, `admin.mappings`, `admin.sessions.revoke`, `admin.status`.

| Rolle | Rechte |
|---|---|
| `viewer` | `library.read` |
| `submitter` | `event.create`, `event.edit`, `dossier.attach`, `comment.write`, `library.read` (nur eigene Entwürfe und eigene Dossiers) |
| `organizer` | Submitter plus `event.publish`, `event.cancel` |
| `editor` | Organizer plus `event.read_all`, `event.restore`, `dossier.read_restricted`, `library.manage`, `format.manage`, `series.manage`, `offer.manage`, `import.review`, `import.manage`, `taxonomy.manage`, `venue.manage` (global, überall) |
| `stupa` | `event.read_all`, `comment.write`, `library.read` (Leser) |
| `member` | `library.read` |
| `admin` | wie heute |

Die Eigen-Regel "eine Rolle unterhalb `event.submit` arbeitet nur an eigenen Dossiers" (`orgs/scope.py` `restricted_to_own`, `dossier/rules.py` `ensure_permission`) wird an `event.publish` festgemacht (Builder ändert die Quelle, die Wirkung bleibt). Wo bisher `event.submit` Aktionen freigab (`verify-howto`, `save-as-format`, `outcome`, Klon-Rechte, `formats/access.py`, `archive/access.py`), gilt nun `event.publish`; `event.approve` in `confirm-location` wird `event.publish`. "Als Format speichern" bleibt wie D9: Organizer der Organisation und Redaktion.

### 4.3 Routen-Inventur

`tests/unit/test_route_authz_inventory.py` (`ROUTE_PERMS`) führt jede entfernte Route nicht mehr und jede neue (Abschnitt 7) mit ihrem Recht. Der Test bleibt der Wächter: neue Route ohne Eintrag fällt durch, entfernte mit Rest-Eintrag ebenfalls. Die Meta-Tests des Tests laufen unverändert.

## 5. Entfernen (Liste, bindend)

### 5.1 Backend

| Was | Aktion |
|---|---|
| `pipeline/transitions.py` (T00 bis T12 als Daten), `pipeline/decision.py`, `pipeline/guards/` (`common`, `content`, `fields`, `media`, `timing`, `__init__`), `pipeline/fieldclass.py`, `pipeline/allowed.py` (Aktionsliste -> neue `events/allowed.py`, 7.2), `pipeline/advance.py` (Logik -> `worker/advance.py`), `pipeline/livecheck.py`, `pipeline/marks.py` (Flyer, `acknowledge-changes`), `pipeline/notices.py`, `pipeline/reasons.py`, `pipeline/exception.py`, `pipeline/assign.py`, `pipeline/values.py`, `pipeline/schemas.py`, `pipeline/snapshot.py` (`Snapshot`/`Actor`), `pipeline/router.py` (`transitions/{t}`, `guards/{t}`) | **löschen**. Die Datei `pipeline/service.py` (`fire`) und `actions_service.py` gehen in das neue Modul `events/lifecycle.py` auf (eine Datei je Übergang-Gruppe, klein, kein Datengetriebenes `TRANSITIONS`) |
| `pipeline/actions.py` (`run_actions`, `invalidate_feed_cache`, `ensure_derivatives`, `invalidate_public`, `request_rebuild`), `pipeline/actor.py`, `pipeline/slugs.py`, `pipeline/revert.py` | **bleiben**, ziehen um nach `events/postcommit.py` (Actions), `events/slugs.py`, `events/revert.py`; `pipeline/` verschwindet als Paket |
| `pipeline/actions_router.py`: `/actions/image-exception`, `/actions/assign-organization`, `/actions/acknowledge-changes`, `/actions/confirm-flyer`, `/actions/cancel|postpone|reinstate` unter `/events/{id}/actions/…` | `image-exception`, `assign-organization`, `acknowledge-changes`, `confirm-flyer` **löschen**; `cancel`, `postpone`, `reinstate` wandern auf `/events/{id}/cancel|postpone|reinstate` (7.1); `revert-revision` bleibt als Verlaufsfunktion (7.1) |
| `events/location_router.py` (`/actions/confirm-location`) | **bleibt** (Feed-Datenschutz, M5 2.2), Pfad unverändert, Recht `event.publish` |
| `modules/tasks/` (`router`, `schemas`, `service`) und `GET /api/tasks` | **löschen**, Eintrag in `api_routers.py` |
| `events/board.py`, `view=board` in `events/router.py`, `BoardOut`, `BoardColumn`, `ColumnKey` in `card_schemas.py`, `board()` in `events/listing.py`, `moves`, `next_transition`, `blockers`, `blocker_count`, `allowed_transitions` in `EventCard` und `EventOut`, `TransitionName` | **löschen** |
| `events/schemas.py`: `TransitionIn`, `ImageExceptionIn/Out`, `AssignOrganizationIn`, `LockReason`; `EventOut`: `publishAt`, `textReviewedRev`, `publishedRev`, `flyerCheckedAt`, `imageException`, `submittedBy`, `approvedBy`, `allowedTransitions`, `lockReason` | **löschen** |
| `events/service.py`: Vorschlags-Pfad (`organization_scope_or_proposal`, `proposal_quota`, `_open_proposals`, `editor_four_eyes`); `Create` verlangt eine Organisation im Geltungsbereich von `event.create` (sonst 404) | **löschen/umbauen**; `EventCreate.organizationId` wird Pflicht |
| `events/presenter.py`, `events/access.py`, `events/cards.py`, `events/card_extras.py`, `dossier/guard_data.py`, `dossier/counts.py` | Guard-Snapshot-Bau, `entered_followup_at`, `followup_open` raus; `guard_data.py` schrumpft zum Lader für `hints.py` |
| `events/revisions.py`, `revision_views.py`, `revisions_router.py` | `field_class` raus (Spalte, Parameter `fieldClass`, Filter) |
| `dossier/promote.py` (Anhangs-Hero-Wechsel für `approved`/`live`), `files/attachments.py` Zustandsregeln (Docstring "approved by approvers…"), `events/location.py` (`live`) | auf `published` umstellen, Zustandsprüfungen auf Zweiwerte-Regel (2.4) |
| `dossier/rules.py`: `CLOSED_STATES`, `ensure_open`, Aufruf in `load_for_write` | **löschen** (2.4) |
| `followup/` (`router.py`: `PUT /outcome`, `POST|DELETE /actions/verify-howto`; `outcome.py`, `howto.py`, `missing.py`, `schemas.py`) | `outcome.py` verliert `ensure_outcome_phase` (jetzt: erlaubt, sobald das Event begonnen hat? nein: jederzeit schreibbar, freiwillig); `howto.py` `VERIFY_STATES` fällt weg (`published`, `archived` erlaubt); `missing.py` wird `hints.outcome_open`/`howto_missing` und **gelöscht** |
| `worker/followup.py` (`send_followup_reminders`), Cron in `worker/main.py`, Vorlagen `followup_reminder.*`, `auto_archived.*`, `review_requested.*`, `changes_requested.*`, `task_assigned.*` | **löschen** |
| `notifications/kinds.py`, `recipients.py`, `service.py`, `placeholders.py`: Kinds und Empfängerlogik für `review_requested`, `changes_requested`, `transition_done`, `task_assigned`, `comment_resolved`, `followup_reminder`, `auto_archived` | auf vier Kinds kürzen (Abschnitt 6) |
| `worker/advance.py`: `candidates`, `advance_one`, Zähler `T05/T08/T08b/T09b` | ersetzt durch `archive_ended` (6); `purge_drafts` bleibt |
| `archive/clone.py` (`state="idea"`), `archive/clonable.py` (`OWN_CLONABLE = ("live","followup")`), `search/query.py` (`archived` oder eigene `live`/`followup`), `events/calendar.py` (`withdrawn`-Ausschluss), `events/listing.py` (`archived`/`withdrawn`-Spalten) | Zustandswerte anpassen: Klon legt `draft` an, eigene klonbare Zustände `published`, `archived`; fremde nur `archived`; Kalender und Liste ohne `withdrawn` |
| Einstellung `editor_four_eyes` in `settings.py`, `.env.example`, `deploy/` | **löschen**; neu `publish_requires_editor` (2.2) |
| `public_event_v`, Trigger, Funktionen, Spalten | siehe 2.5 Punkte 5 bis 7 |
| `seeds/dev_events.yaml`, `scripts/seed_dev.py`, `scripts/seed_followup.py`, `tests/fixtures/movienight.yaml`, `scripts/m5_fixture.py` | Zustandsnamen und Wege (`transitions/T..`) auf die neuen Aktionen umstellen; `seed_followup.py` **löschen** |
| `scripts/m3_acceptance.py`, `scripts/m3_worker.py` | **löschen** (nur Pipeline); `m1_acceptance.py`, `m2_acceptance.py`, `m4_acceptance.py`, `m4_ops.py`, `m5_*` bereinigen: Aufrufe von `transitions/…`, Vier-Augen, `imageException` raus; Zeitmuster aus `m3_worker.py` (Uhr setzen) wandert in `acceptance_common.py`, falls `m4_ops`/`m5_*` es nutzen (Builder prüft) |

Rest-Klausel: jedes Symbol, das nach dem Löschen unbenutzt ist (`grep` über `app`, `worker`, `scripts`, `tests`), wird mitgelöscht; `ruff` mit F401/F811 und `basedpyright` sind der Beleg.

### 5.2 Tests (Backend)

Löschen: `tests/unit/pipeline/` komplett (`oracle.py`, `support.py`, `test_actor.py`, `test_advance.py`, `test_board_moves.py`, `test_fieldclass.py`, `test_guards.py`, `test_guards_m3.py`, `test_guards_t09.py`, `test_publish_property.py`, `test_service_write.py`, `test_slugs_actions.py`, `test_transitions_matrix.py`, `test_u_guard.py`); `test_actor`, `test_slugs_actions` (Anteil Slug und Idempotenz), `test_service_write` (Anteil Revision) werden **nicht** gelöscht, sondern nach `tests/unit/events/` verschoben und bereinigt, wo sie noch gelten. Integration löschen: `tests/integration/pipeline/test_four_eyes.py`, `test_full_flow.py`, `test_api_walk.py`, `test_u_guard_integration.py`, `tests/integration/events/test_field_classes_api.py`, `test_board_api.py`, `test_tasks_api.py`, `test_card_guards.py`, `test_rbac_transitions.py`; der Hypothesis-Test "kein `live` ohne Bild" (`test_publish_property.py`) entfällt, ersatzlos. Bereinigen statt löschen: `test_actions.py` (Absage/Verschiebung bleiben), `test_flow.py` (Kurzfluss `draft -> published -> archived`), `test_db_nets.py` (Netze für Trigger weg, Netze für `append_only`, `tzid`, `state` bleiben), `test_advance_states.py` (-> `test_archive_ended.py`), `test_edges.py`, `test_locking_and_fields.py`, `test_rbac_matrix.py`, `tests/unit/shared/test_permissions.py`, `tests/integration/archive/test_followup.py` (-> "So lief es"/`verify-howto`), `test_migration_0006.py` (bleibt, prüft bis `0006`), die Kanarienvogel-Fabrik `tests/_support/canary.py` und `tests/integration/search/corpus.py` (Zustandswerte, `image_exception`).

## 6. Nachbereitung, Benachrichtigungen, Worker

**"So lief es"** ist ein freiwilliger Abschnitt im Dossier: Besucher:innen (`outcome.attendance`), Kosten und Erlös (`outcome.costsCents`, `revenueCents`), Notiz (Dokument `retrospective`), Haken "Anleitung geprüft" (`howto_verified_at/by`, Route `verify-howto` besteht), Verzicht-Begründung entfällt (leer ist erlaubt). Es gibt keinen Zustand `followup`, keinen Abschlussknopf T09, keine Nachbereitungs-Guards (`retrospective_filled`, `outcome_set_or_waived`, `howto_verified`, `checklist_done_followup`). Das Kennzeichen "Anleitung ungeprüft" (`howto_unverified`) bleibt informativ in Dossier, Liste und Archiv; `Format.last_verified_at` wird beim Haken gesetzt (`formats/verification.py` unverändert), mit der Rechteprüfung aus 8, Nr. 6. Checklisten-Phasen `planning, review, live, followup` bleiben als Gruppierung der Punkte (nur Beschriftung; die Seeds `seeds/checklists.yaml` bleiben).

**Kinds** (`notifications/kinds.py`): `comment_added` (Mail), `published` (Mail), `cancelled` (Mail), `checklist_due` (Mail). Keines ist `essential`. `published` geht an die Redaktion und die Mitglieder der Organisation (ohne den Auslöser); `cancelled` zusätzlich an den Ersteller; `comment_added` und `checklist_due` wie heute. Neue Vorlagen `published.*` und `cancelled.*` (Betreff, Text, HTML) unter `notifications/templates/de/`; `comment_added.*` und `checklist_due.*` bleiben. Konto-Einstellungen (`features/account/notification-prefs`) zeigen die vier.

**Worker**: `worker/advance.py` bekommt `archive_ended(ctx, now)`: alle `published`-Events mit `ends_at + 12 h <= now` (auch abgesagte) werden im eigenen Session und Commit archiviert (Aktion `archive`, `actor_type = 'system'`, Feed-Invalidierung wie heute), in Seiten von `BATCH = 200`, ein Fehler stoppt den Lauf nicht; Cron wie `advance_states` alle 15 Minuten, `unique=True`. `purge_drafts` bleibt. `send_followup_reminders` fällt weg. Die Rückgabe-Zeile für das arq-Log heißt `archived=N failed=N`.

## 7. API-Vertrag (camelCase)

### 7.1 Neu und geändert

| Route | Zweck |
|---|---|
| `POST /api/events/{id}/publish` | Body `{}`; Header `If-Match`; Antwort `EventOut` |
| `POST /api/events/{id}/unpublish` | Body `{}`; Antwort `EventOut` |
| `POST /api/events/{id}/archive` | Body `{}`; Antwort `EventOut` |
| `POST /api/events/{id}/restore` | Body `{}`; Antwort `EventOut` (Zustand `draft`) |
| `POST /api/events/{id}/cancel` | Body `CancelIn {reason?, publicReasonCode, publicReasonText?}` wie `actions_router.py` heute |
| `POST /api/events/{id}/postpone` | Body `PostponeIn {…, newStartsAt?, newEndsAt?}` |
| `POST /api/events/{id}/reinstate` | Body `ReinstateIn {reason?}` |
| `GET /api/events/{id}/hints` | `{ items: [{code, severity, field}] }` aus `missing_info` (Recht: Lesen des Dossiers, 404 sonst) |
| `GET /api/events?state=&organization=&category=&mine=&q=&from=&to=&sort=&limit=&offset=` | `state` mehrfach aus `draft`, `published`, `archived`; `view=list` (Standard) oder `view=calendar`; `view=board` und `columnLimit` entfallen. Jahr-Chip im Client über `from`/`to` |
| `POST /api/events/{id}/actions/revert-revision` | bleibt, Pfad **unverändert** (Verlaufsfunktion), läuft durch dieselben Ableitungen wie `PATCH` (Ort, Fakten, Ganztag; 8, Nr. 2) |
| `PATCH /api/events/{id}` | `EventPatch` bekommt `organizationId` (nur Redaktion, nur solange leer; ersetzt `assign-organization`) |

`EventOut` neu: `allowedActions: list[Literal["publish","unpublish","archive","restore","cancel","postpone","reinstate","revert-revision","confirm-location","verify-howto","save-as-format","clone"]]`, `editableFields`, `hintCount` (Anzahl `warn`), `poster`, `rev`; entfernt wie 5.1. `EventCard`: `hasPoster`, `publicStatus`, `state` (drei Werte), `organization`, `venueLabel`, `primaryCategory`, `allDay`, `formatSlug`, `howtoUnverified`, `openQuestions`; entfernt `blockers`, `blockerCount`, `moves`, `nextTransition`, `allowedTransitions`, `publishAt`. `CalendarOut` unverändert bis auf die Zustandswerte.

### 7.2 Entfernte Routen

`POST /api/events/{id}/transitions/{transition}`, `GET /api/events/{id}/guards/{transition}`, `GET /api/tasks`, `GET /api/events?view=board`, `POST /api/events/{id}/actions/{image-exception, assign-organization, acknowledge-changes, confirm-flyer}`, `POST /api/events/{id}/actions/{cancel, postpone, reinstate}` (verschoben auf 7.1), `GET /api/events/{id}/revisions?fieldClass=`. Die Inventur 4.3 und `docs`/OpenAPI ziehen nach.

### 7.3 Unverändert

Feed `GET /api/public/feed/events` (Schema 2, Cursor, `since`), `GET /ics/all.ics`, `GET /ics/k/<slug>.ics`, Archiv, Klon, Formate, Bibliothek, Suche, Kalender, Anhänge, Dokumente, Checkliste, Kommentare, Angebote, Mailvorlagen, Verwaltung, Konto, Sitzungen, Audit. Der Feed und die ICS lesen `published` statt `live` (und `archived`); `followup` gibt es nicht mehr. `HEAD` kommt neu dazu (8, Nr. 10).

## 8. Reste aus `docs/M5-REVIEW-OFFEN.md`

| # | Befund | Noch relevant | Zuordnung und Auftrag |
|---|---|---|---|
| 1 | Cache wird bei Orts-, Organisations-, Kategorie-Änderung und Scan-Urteil nicht invalidiert (`venues_router.py`, `organizations_router.py`, `categories_router.py`, `worker/scan.py`) | **ja** | backend: `invalidate_public` nach Commit in jedem Admin-Schreibpfad der View-Quellen und nach Scan-Urteil eines Posters eines öffentlichen Events; je ein Test (Ort privat schalten, Organisation umbenennen, infiziertes Poster) liest den Feed direkt danach |
| 2 | `revert` überspringt die Ableitungen (Ort, Fakten, `all_day`, `starts_on/ends_on`) | **ja**, bleibt als Verlaufsfunktion | backend: `revert.py` ruft dieselbe `derived_values`/`allday.resolve`-Kette wie `EventService.patch`; Test mit `venue_text`-Wechsel an `published` (Feed ohne `venueText`) |
| 3 | Palette zeigt "Neues Dossier"/"Aus Vorlage" ohne `event.create` | **ja** | frontend: `a:new`, `a:template` mit `auth.can('event.create')`, `a:format` mit `allowedActions` `save-as-format`; Specs für `member` und `viewer` |
| 4 | Strg/Cmd+K in Rahmen ohne Palette | **ja** | frontend: nur im Rahmen `rail`/angemeldet, `isOpen` beim Rahmenwechsel zurücksetzen |
| 5 | Palette: Liste scrollt nicht mit, Suchfehler 429/503 als "Keine Treffer" | **ja** | frontend: `scrollIntoView({block:'nearest'})`, eigener Fehlerzustand |
| 6 | `verify_format` bei fremdem Format-`format_id` ohne Rechteprüfung (heute T09 und `verify-howto`) | **ja**, nur noch über `verify-howto` | backend: `verify_format` nur mit `event.publish` oder `format.manage` für die Organisation des Formats, sonst nur das Event-Kennzeichen; Cross-Org-Test |
| 7 | Erinnerungsmail "Es fehlt noch: ." | **nein** (`followup_reminder` fällt) | entfällt mit 6 |
| 8 | Redis-Claim vor Commit (`worker/followup.py`) | **nein** für diese Datei; **Builder prüft**, ob `send_due_reminders`/`dossier/checklist_due.py` dasselbe Muster haben | backend: Claim erst nach Commit oder im Fehlerzweig löschen, falls ja |
| 9 | ICS: `tzid` ohne CHECK | **ja** | backend: `ck_event_tzid` in 0007 (2.5 Punkt 4); Unit-Test mit fremdem `tzid` in `ics_row` (grobe Schreibweise: überspringen oder 'Europe/Berlin') |
| 10 | Kein `HEAD` für ICS und Feed, Negativ-Cache für unbekannte Slugs | **ja** | backend: `api_route(methods=["GET","HEAD"])`; kurzer Negativ-Cache oder nginx `limit_req` (Entscheidung beim Builder, dokumentiert) |
| 11 | Kanarienvogel deckt Format-Pfad nicht ab (`format.description_md`, Master-Anleitung, `defaults`, Org-Kontakt); Ziffernmarke `987654` flackert | **ja** | backend: `tests/_support/canary.py` um `CANARY-INTERNAL-FORMATDESC/-FORMATDEFAULTS/-MASTERHOWTO` ergänzen, Betragsmarke nicht hexartig (11 Ziffern); Test auf Feed, ICS, Medien |
| 12 | Klon aus fremder Vorlage übernimmt `protocolOwner`, `priceText`, `meetingPoint`, `agendaMd` | **ja** | backend: `events/facts.py` und `archive/carry_over.py`: bei `relation == 'foreign'` nur Kapazität, Altersgrenze, Min/Max-Teilnehmende; Berichtszeile nennt, was bleibt; `test_facts_reset` erweitern |
| 13 | Klon aus fremder Vorlage zieht Inline-Bilder (`/api/media/images/<uuid>`) per `add_refs` hinein | **ja** | backend: bei `foreign` Bildlinks aus `description_md` entfernen oder keine Refs; Test mit Inline-Bild |
| 14 | Klon-Dialog: Pflichtzeit bei ganztägiger Vorlage, Organisationsliste nicht aus `event.create` | **ja** | frontend: Zeitfeld bei `allDay` ausblenden (12:00 lokal senden), `orgOptions` aus den Organisationen mit `event.create`; backend: Vorschau liefert die erlaubten Organisationen, falls `auth/me` es nicht hergibt (Builder prüft) |
| 15 | `.github/CODEOWNERS` Platzhalter | **ja**, nicht durch Builder lösbar | **Luis** liefert das Team-Handle; bis dahin bleibt es in "Offen" der Abnahme |
| 16 | Weitere Punkte "Integration M5 offen": Import in Thunderbird/Google/Apple nicht geprüft | **ja** | Luis/Redaktion (Schrittfolge `M5-ABNAHME.md` T); Zeile bleibt offen |
| 17 | D8 (beide Durchläufe der wiederholten Stunde in UTC) ohne Luis' Okay | **ja** | Luis entscheidet; Rücknahme = eine Zeile in `ics/timezone.py` plus Golden |
| 18 | Viewer sieht Kosten der eigenen Organisation (`Letztes Mal`) | **ja** | Luis entscheidet (13.1 O2); Builder ändert nichts |
| 19 | Ausstehender Anhang eines fremden Dossiers: 404, Vertragstext 409 | **ja** | backend: Verhalten bleibt 404 (404-Regel), Vertragsabweichung im Abnahmeprotokoll nachführen |
| 20 | Movienight-Bestand synthetisch, Poster je Dossier eigene Datei | **ja**, aber der Bestand wird neu geschrieben | backend: `movienight.yaml` und `m5_fixture.py` auf neue Zustände; keine Änderung am Prinzip |
| 21 | Vollsuite nach letzter Änderung nicht erneut gelaufen | **ja** | Integration: Vollsuite plus Gates im Abnahmeschritt (10) |
| 22 | Pilotkriterien ("Idee bis Archiv", 10 Events mit Bild) nicht aus dem Repo prüfbar; `pilot_check.py` ungelaufen | **ja**, Wortlaut ändert sich | Integration: Pilotkriterium wird "Dossier anlegen bis Archiv", `pilot_check.py` zählt `published` mit Poster; Lauf gegen Ziel-Instanz bleibt Luis |
| 23 | PLAN §18 Minor 2 und 3 offen | **ja**, unberührt | bleibt in "Offen" |
| 24 | Frontend-Bundle wuchs auf 633,74 kB; axe lief gegen `ng serve` | **ja** | frontend: Budget nach dem Rückbau messen; der Rückbau soll es senken (Board, Aufgaben, Dialoge); axe zusätzlich gegen den Produktions-Build hinter nginx, falls der Stack läuft |
| 25 | `m5_acceptance` legt je Lauf etwa 60 Dossiers an | **ja** | Integration: `m5b_acceptance.py` räumt seine Dossiers (`created_by = 'm5b-…'`) per SQL-Skript am Ende oder bietet `--clean` |
| 26 | Branch `feat/m5-archiv` anlegen, nichts committet | **erledigt** (HEAD `aebf331`) | entfällt |

## 9. Tests

**Backend neu**
- `tests/unit/events/test_lifecycle_matrix.py`: reine Matrix **3 Zustände x 7 Aktionen** (`publish`, `unpublish`, `archive`, `restore`, `cancel`, `postpone`, `reinstate`) gegen die Rollen `submitter` (eigenes/fremdes Dossier), `organizer` (eigene/fremde Organisation, Letzteres 404), `editor`, `stupa`, `viewer`, `member`, `admin`; erwartet 200/403/404/409 und den Zielzustand; dazu `publish_requires_editor = true`. Eine kleine Tabelle statt `oracle.py`.
- `tests/unit/events/test_hints.py`: jeder Code aus 3.2 einzeln und kombiniert; `missing_info` ist rein.
- `tests/unit/events/test_publish_incomplete.py`: nur `title`, `starts_at`, `organization` zählen.
- `tests/integration/events/test_lifecycle_api.py`: Pfad `draft -> published -> cancelled -> reinstate -> unpublish -> archive -> restore`, Revisionen und Verlauf (`event_status_event`) je Schritt, ETag/`If-Match`, `invalidate_feed_cache` aufgerufen.
- `tests/integration/pipeline/` entfällt; `tests/integration/events/test_archive_ended.py`: Worker archiviert 12 h nach Ende, nicht früher, auch abgesagte; ein Fehler stoppt nicht.
- `tests/integration/test_migration_0007.py`: Datenbank auf `0006` migrieren, **je ein Event in jedem der acht Altzustände** (`idea, planning, in_review, approved, live, followup, archived, withdrawn`) per SQL einfügen, dazu `approver`-Gruppenzuordnung und `-`Mitgliedschaft, Benachrichtigungen mit entfernten Kinds, ein Event ohne Organisation in `idea`; `upgrade head`; erwartet Zielzustand je Zeile (Abschnitt 2.5), eine `event_status_event`-Zeile je geändertem Event, Rollen, gelöschte Spalten/Trigger/Funktionen (`information_schema`, `pg_trigger`, `pg_proc`), View-Inhalt (`live` erscheint, `approved` nicht), `ck_event_tzid`, Feed liefert `image: null` für ein `published`-Event ohne Poster. Muster `test_migration_0006.py`.
- Feed/ICS: `test_feed_v2.py`, `test_ics_routes.py`, `test_snapshot.py`, `test_view.py`, `test_cache_invalidation.py`, `test_canary.py`, `test_schemathesis.py` und die Unit-Tests `unit/publicapi/**` mit den Golden-Dateien bleiben **grün und unverändert in der Aussage**; nur die Fabriken stellen auf `published` um. Neu: Feed-Zeile ohne Poster, mit `persons_depicted` ohne Einwilligung, `HEAD`.
- Berechtigung: `test_permissions.py`, `test_rbac.py`, `test_route_authz_inventory.py`, `test_membership_sync.py`, `test_group_mapping_api.py` auf Katalog 4.2 und ohne `approver`.

**Frontend**
- Jest-Specs der gelöschten Komponenten fallen mit ihnen. Neue/angepasste Specs: Dossierseite (Anker-Navigation, Poster-Slot leer/belegt, Hinweisbanner), Aktionsleiste je `allowedActions`, kleiner Absage/Verschiebungs-Dialog, Hinweisliste, Liste mit Chips und Umschalter, Palette (3, 4, 5 aus Abschnitt 8), Klon-Dialog (14). `translations.spec.ts` bleibt der Wächter gegen tote Schlüssel.
- Playwright `e2e/m5b.spec.ts` (Hell und Dunkel, 360 px und Desktop, axe, wie `m5.spec.ts`):
  1. `organizer-fsi`: Dossier anlegen -> Anleitung schreiben (Abschnitt Doku) -> Poster per Drag & Drop -> Veröffentlichen -> Event steht in `GET /api/public/feed/events` mit Bild.
  2. `organizer-fsi`: zweites Dossier **ohne Poster** veröffentlichen -> Hinweisbanner "Ohne Bild nicht bewerbbar" sichtbar, Feed `image: null`.
  3. "Neu aus Vorlage": aus der Liste einen archivierten Event als Vorlage klonen, das neue Dossier ist `draft` und trägt die kopierte Anleitung.
  4. Weitere kurze Fälle: Absagen (Feed `cancelled`), Zurückziehen (verschwindet aus dem Feed), `editor` stellt wieder her, `publish_requires_editor` ist per Dev-Einstellung nicht Teil des Browser-Tests (nur Backend).
- Alte Specs **bereinigen statt löschen**: `m1.spec.ts` (Login, Rolle aus Gruppe bleibt; "kann nicht freigeben" und "Freigabe ohne Poster" entfallen), `m2.spec.ts` (Verwaltung, Mapping, 404 fremde Organisation, Sitzungen bleiben; `trusted`-Teile raus), `m3.spec.ts` (Board, Aufgaben, Übergangs-Dialoge, Feldklassen raus; Autosave, Konflikt-Dialog, Verlauf, Handy bleiben und ziehen auf die Dossierseite um), `m4.spec.ts` (Anhänge, Anleitung, Checkliste, Kommentare, Mails, Inbox bleiben; Zustandswege auf neue Aktionen), `m5.spec.ts` (Klon, Format, Bibliothek, Suche, Palette, Kalender bleiben; Nachbereitung-Reiter -> Abschnitt "So lief es"). Hilfsfunktionen in `e2e/support/dossier.ts` laufen über die neuen Routen.

## 10. Frontend (Struktur)

### 10.1 Dossierseite `/dossiers/:id`

Eine Seite statt Liste+Detail nebeneinander und Reitern. Aufbau von oben:

1. **Kopf** (`head/`): Titel (bearbeitbar), Zustand als Text (nie nur Farbe: "Entwurf", "Veröffentlicht", "Archiv", dazu "Abgesagt"/"Verschoben"), Datum, Organisation, Ort, Kategorie. Aktionsleiste je `allowedActions`: Veröffentlichen, Zurückziehen, Absagen/Verschieben/Wieder ansetzen (kleiner Dialog mit Grund-Enum und Text), Archivieren, Wiederherstellen (Redaktion), Neu aus Vorlage (öffnet `dossiers/neu?vorlage=<id>`). Dazu die Hinweisleiste (`hints`, Zahl und aufklappbare Liste) und der Autosave-Indikator.
2. **Poster-Slot** (3.1).
3. **Anker-Navigation** (klebt oben beim Scrollen, Tastatur erreichbar): Doku, Anhänge, Checkliste, Mails, Angebote, So lief es, Verlauf. Dazu vor "Doku" der einklappbare Abschnitt **Eckdaten** (das Formular `form/`, Beschreibung, Links, Kosten, Fakten): bei `draft` offen, bei `published` und `archived` zu (Annahme).
4. **Abschnitte** in dieser Reihenfolge, jeder mit `id` für den Anker: Doku/How-to (heute `howto/howto-tab`, Dokument-Editor), Anhänge (`attachments/` mit Drag & Drop), Checkliste (`checklist/`), Mails (`mails/`), Angebote (`attachments/quotes-section`), So lief es (`followup/outcome-form`, `retrospective`, `howto-check`), Verlauf und Kommentare (`history/`, `activity/`: Zeitleiste, Revisionsvergleich, Kommentarfäden, Rückfrage-Schaltflächen).
5. Der Konfliktdialog (`conflict/`), der Austritts-Wächter (`pending-changes.guard`) und der Fokus-Sprung auf Felder (`detail/focus-field`) bleiben.

### 10.2 Liste `/dossiers`

`list/dossier-list` wird eine Seite ohne Detail-Spalte: Kopf mit "Neues Event" und "Neu aus Vorlage" (gleichwertig, beide sichtbar), Filterchips **Organisation, Kategorie, Zustand, Jahr** (Zustand: Entwurf, Veröffentlicht, Archiv, dazu "Abgesagt"; Chip-Zustand in der URL, `shared/url-state.ts`), Umschalter **Liste | Kalender** (`?ansicht=kalender`). Die Karten tragen Thumbnail oder Platzhalter, Titel, Datum, Organisation, Zustandstext, ein Symbol bei `warn`-Hinweis. Der Kalender ist die vorhandene Komponente (`features/calendar/page/calendar-page.component` wird zur eingebetteten Ansicht, Route `/kalender` entfällt).

### 10.3 Navigation

Events (`/dossiers`), Formate, Bibliothek, Archiv/Suche (`/archiv`), Verwaltung (nur mit Recht), Konto; Handy: dieselben, unter "Mehr" nach Priorität (`layout/nav.service.ts`, `bottom-bar`, `nav-rail`). `homeRedirectGuard` leitet nach `/dossiers`. Inbox-Glocke (`features/notifications`) bleibt, mit vier Kinds. Palette-Gruppen bleiben, die Navigationsziele folgen der neuen Liste.

### 10.4 Löschen (Frontend)

Verzeichnisse: `features/pipeline/**` (Board, Karte, Filter, Move-Sheet), `features/tasks/**`, `features/dossiers/transition/**`, `features/dossiers/exception/**`, `features/dossiers/assign/**`, `features/dossiers/reason/**` (nur von den Übergangs-Dialogen und `tasks` benutzt; der kleine Absage-Dialog nutzt `cancel/`), `features/dossiers/followup/followup-tab.*` (Inhalt zieht in den Abschnitt), `features/dossiers/overview/dossier-overview.*` (Inhalt zieht in Eckdaten und Kopf; `last-time-block` und `template-panel` bleiben als Abschnittsteile), `features/dossiers/detail/detail-dialogs.*` (Dialoge I13 bis I15; `cancel/` bleibt), `shared/ui/guard-list/**` (ersetzt durch Hinweisliste), `shared/ui/pipeline-board/**`. Dateien: `features/dossiers/api/{board.models,task.models,transitions,transition-label}.ts`, Anteile in `action.models.ts`, `dossier-commands.ts`, `problem-message.ts`, `event.models.ts`, `core/api/models.ts` (`trusted`, Übergangs-Typen), `shared/ui/index.ts`-Exporte, `app.routes`/`feature-routes.ts` (Einträge `aufgaben`, `pipeline`, `kalender`, Route `dossiers/:id/nachbereitung`), i18n: `translations.pipeline.de.ts` (komplett, soweit nicht Zustandstexte und Hinweise nach `translations.dossier.de.ts` ziehen), tote Schlüssel in `translations.events.de.ts`, `translations.dossier.de.ts`, `translations.shell.de.ts`. `translations.spec.ts` findet verwaiste Schlüssel; `npm run lint` mit `no-unused` ist der zweite Beleg.

## 11. Abnahme M5b (wörtlich)

> Ein Event lässt sich ohne Pipeline von Entwurf bis Archiv führen: Organisation legt es an, schreibt die Doku, lädt ein Poster hoch und veröffentlicht selbst; ohne Poster lässt es sich veröffentlichen und zeigt den Hinweis "Ohne Bild nicht bewerbbar", der Feed liefert dann `image: null`. Zurückziehen, Absagen, Verschieben, Wiederansetzen, Archivieren (von Hand und 12 h nach Ende durch den Worker) und Wiederherstellen (Redaktion) funktionieren mit den Rechten aus 2.2. "Neu aus Vorlage" steht neben "Neues Event" und legt einen Entwurf an. Migration `0007` überführt alle acht Altzustände auf drei, der Rest der Datenbank bleibt gültig. Feed, ICS, Archiv, Formate, Bibliothek und Suche laufen unverändert (Golden-Tests, Schemathesis, Kanarienvogel grün). Es gibt keine Route, keine Komponente, keinen Test, keinen i18n-Schlüssel und keine Spalte der entfernten Pipeline mehr.

Prüfpunkte der Integration (Skript `backend/scripts/m5b_acceptance.py` gegen den Dev-Stack mit echten OIDC-Logins, schreibt `docs/M5B-ABNAHME.md`; nie gegen Live):

| # | Prüfpunkt | Beleg |
|---|---|---|
| a | Pfad `organizer-fsi`: anlegen, Doku, Poster, `publish`, im Feed; ohne Poster: `image: null`, `GET /hints` nennt `no_poster` | HTTP |
| b | Rechte: `submitter` kann nicht veröffentlichen (403), `organizer` fremder Organisation 404, `editor` darf alles; `publish_requires_editor = true` sperrt `organizer`; `restore` nur `editor` | HTTP |
| c | `cancel`, `postpone`, `reinstate`: Feed `publicStatus`, ICS `STATUS:CANCELLED`/`TENTATIVE`, `SEQUENCE` steigt | HTTP + ICS |
| d | Worker: Uhr gesetzt, `archive_ended` archiviert nach Ende + 12 h; Doku im Archiv weiter beschreibbar; Eckdaten 409 | HTTP + Log |
| e | Migration `0007`: Test aus Abschnitt 9 und `alembic upgrade head` auf der Dev-DB, danach Zahlen je Zustand | Skript |
| f | Entfernte Routen antworten 404 (`/api/tasks`, `/transitions/…`, `/guards/…`, `?view=board`); Inventur grün | HTTP + Test |
| g | Suche, Klon, Formate, Bibliothek: bestehende Abnahmepunkte aus `m5_acceptance` (a, b, i) bestehen auf den neuen Zuständen | HTTP |
| h | Feed-Cache: Veröffentlichen löst Neuaufbau aus; Orts-, Organisations-, Kategorie-Änderung und Scan-Urteil invalidieren (8, Nr. 1) | HTTP + Redis |
| i | Browser: `e2e/m5b.spec.ts` und bereinigte `m1` bis `m5`, 360 px und Desktop, Hell und Dunkel, axe, Tastaturpfade (Anker-Navigation, Aktionsleiste, Palette) | Playwright |
| j | Gates: Backend `ruff`, `basedpyright`, `pytest -m 'not integration and not e2e and not live'`, `pytest -m integration` (**Vollsuite**), Frontend `lint`, `typecheck`, `npm test`, `build` (Bundle <= 633,74 kB, Soll darunter), `deploy/compose-lint.sh`, `backup.sh` plus `restore-smoke.sh` mit Revision `0007_event_dossier` | Skripte |
| k | Aufräumprobe: `grep -rn` (Backend, Frontend, Skripte, Tests, i18n) nach `in_review`, `followup`, `withdrawn`, `T0[0-9]`, `T1[0-2]`, `fourEyes`, `four_eyes`, `imageException`, `image_exception`, `fieldClass`, `field_class`, `approver`, `trusted`, `/api/tasks`, `view=board` findet nur Migrationen `0001` bis `0007`, Verlaufstexte (Verlauf zeigt Altzustände) und frühere Kontrakte/Abnahmen | Befehl im Protokoll |

Das Protokoll listet außerdem die offenen Punkte aus 8, die nicht Builder-Sache sind (15, 16, 17, 18, 22, 23), und die Entscheidungen aus 13.

## 12. Doku und Skills

`CLAUDE.md` ("What this is", Skill-Liste, Befehle), `README.md` und die Skills unter `.claude/skills/`: `be-pipeline` -> **ersetzt** durch `be-lifecycle` (drei Zustände, Übergänge, `missing_info`, Worker `archive_ended`), `be-events` (Zustände, View, Poster optional), `be-archive` (Nachbereitung als Abschnitt), `be-notifications` (vier Kinds), `be-auth` (Rollen ohne `approver`), `frontend` (Dossierseite, Liste), `conventions` (Migrationsregel gilt weiter). `docs/M1..M5-KONTRAKT.md` bleiben unverändert als Geschichte; `M5B-KONTRAKT.md` führt die Abweichungen (13.2). `PROVENANCE.json`: Einträge für gelöschte Dateien entfernen, für verschobene den neuen Pfad eintragen (`tests/unit/test_provenance.py` ist der Wächter).

## 13. Entscheidungen und Abweichungen

### 13.1 Offen für Luis (Vorschlag steht im Kontrakt, Builder baut den Vorschlag)

- **O1 Einwilligung bei Personenfotos**: `persons_depicted` ohne Einwilligungsnotiz bleibt Bedingung dafür, dass ein Poster im Feed erscheint (Datenschutz), Hinweis `poster_consent_missing`. Alternative: ganz ohne Bedingung (Hinweis genügt).
- **O2 Kosten für `viewer`** der eigenen Organisation: unverändert wie M5 (`Letztes Mal` zeigt Kosten der eigenen Organisation); Alternative: nur Organizer und Redaktion.
- **O3 `publish_requires_editor`** als Umgebungsvariable (Neustart nötig) statt Verwaltungs-Schalter in der Datenbank. Alternative: Tabelle `setting` mit Seite in der Verwaltung.
- **O4 Wiederherstellen** führt nach `draft` (Event verlässt den Feed bis zur neuen Veröffentlichung). Alternative: zurück nach `published`.
- **O5 Archiv bleibt für die Doku beschreibbar** (2.4). Alternative: Archiv schließt, "So lief es" nur bis zum Archivieren (Worker nach 7 Tagen statt 12 h).
- **O6 Zeitgesteuertes Veröffentlichen** (`publish_at`) entfällt. Alternative: Spalte und eine Minute im Worker behalten.
- **O7 Eckdaten-Abschnitt** einklappbar vor der Doku (10.1 Punkt 3); Alternative: Eckdaten im Kopf aufklappen.
- **O8 Org-lose Altentwürfe** bleiben nur für die Redaktion sichtbar, die Organisation per `PATCH` zuweisen kann; Vorschläge ("Event vorschlagen" ohne Organisation) gibt es nicht mehr.

### 13.2 Abweichungen von PLAN und M1 bis M5 (zur Nachführung durch Luis)

1. PLAN §4 (Zustände `idea` bis `withdrawn`, T00 bis T12), §5.3 (Rolle `approver`, `trusted`), §15.1 I02, I03, I13, I14, I15 und das Guard-System PLAN §4.4 entfallen; `event.submit` und `event.approve` werden `event.publish`.
2. M3-Abweichungen und M5 2.2 "Bild Pflicht (E41)" werden aufgehoben; `attachment_poster_ok` ist weicher (2.5 Punkt 6).
3. M5 13.1 Nr. 13 (T07 ohne `STATUS:CANCELLED`): `unpublish` verhält sich wie T07 (Zeile verlässt die View).
4. Aus M5 2.4 (T08/T09/T09b, `followup`) bleibt nur der Gedanke der Nachbereitung als freiwilliger Abschnitt; `followup_reminder` und `auto_archived` fallen.

## 14. Verzeichnisbesitz

Zwei Builder, jeder schreibt nur in seinen Bereich; Konflikte löst die Orchestrierung. Kein Commit und kein Push vor dem Review; im letzten Schritt entsteht `feat/m5b-vereinfachung` mit gescopten Commits (`refactor(events)`, `feat(events)`, `feat(db)`, `feat(frontend)`, `test`, `docs`). Werkzeuge und Fallen wie `docs/M3-ABNAHME.md`, `M4-ABNAHME.md`, `M5-ABNAHME.md`: `nix run nixpkgs#ruff`/`#basedpyright`, `pytest` mit `LD_LIBRARY_PATH` (libstdc++, libmagic), Playwright-Browser über `nix build nixpkgs#playwright-driver.browsers`, Dienste über `deploy/dev-up.sh`, nach Codeänderung `systemctl --user restart stupa-api stupa-worker`, im Frontend `stupa-ng`. Die Migration läuft über die Units (`dev-up.sh`), nicht von Hand gegen fremde Datenbanken.

| Builder | Besitzt | Aufgaben |
|---|---|---|
| **backend** | `backend/**` (Module, `migrations/versions/0007_event_dossier.py`, `seeds/`, `scripts/`, `worker/`, `tests/`), `deploy/**`, `.env.example`, `.github/workflows/ci.yml`, `.claude/skills/be-*/`, `CLAUDE.md`, `README.md`, `PROVENANCE.json` (Backend-Einträge), `docs/M5B-ABNAHME.md` (Abschnitte Backend), Abschnitte 2 bis 8 (Backend-Teile), 9 (Backend), 12 | Migration, Lebenszyklus, `hints`, Rechte, Worker, Kinds, Feed/View, Skripte, Review-Reste 1, 2, 6, 8 (Prüfung), 9 bis 13, 19, 20, 25 |
| **frontend** | `frontend/**` (`src/app/**`, `e2e/**`, `src/locale`/i18n-Dateien, Jest-Specs), `.claude/skills/frontend/`, `PROVENANCE.json` (Frontend-Einträge) | Dossierseite, Poster-Slot, Hinweisliste, Aktionsleiste, kleiner Absage-Dialog, Liste mit Chips und Kalender-Umschalter, Navigation, Palette, Klon-Dialog, Löschliste 10.4, Review-Reste 3, 4, 5, 14, 24, Playwright `m5b` und Bereinigung `m1` bis `m5` |
| **Integration** (Orchestrierung, kein dritter Builder) | Verdrahtung, `scripts/m5b_acceptance.py`, `docs/M5B-ABNAHME.md`, Branch und Commits | Abschnitt 11, Gates, Aufräumprobe, offene Punkte für Luis |

Schnittstelle zwischen den Buildern ist allein Abschnitt 7 (OpenAPI). Das Backend liefert zuerst Migration, Lebenszyklus-Routen und `EventOut`/`EventCard` im neuen Zuschnitt, das Frontend kann dagegen bauen; bis dahin entwickelt es gegen `?demo`-lose Mock-Typen aus 7.1.
