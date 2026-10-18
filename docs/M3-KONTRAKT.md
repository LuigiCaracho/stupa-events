# M3-Kontrakt: Pipeline vollständig

Verbindlich für die zwei Builder von M3 (**backend**, **frontend**). Quellen: `PLAN.md` §3.3 (`event`, `event_revision`, `event_status_event`), §3.5, §4 komplett, §5.2 bis 5.4, §15.1 (I02, I03, I04, I05, I07, I13, I14, I15), §16.1 (Zeile M3), Entscheidungslog E02 bis E09, E21 (Autosave), E07 (Feldklassen), E41, `ENTSCHEIDUNGEN.md`, `docs/M1-KONTRAKT.md` und `docs/M2-KONTRAKT.md` (gelten weiter, ihre Abweichungslisten ebenso), `docs/M2-ABNAHME.md` Abschnitt "Offen", `CLAUDE.md`, die Skills unter `.claude/skills/*`, Upstream `STUPA-Workflow@93c33d6` (U) für Muster (`U frontend/src/app/pages/todos/board-view/*` Board mit CDK-Drag, Tastatur und Phone-Tabs; `U backend/app/modules/flow/dispatch.py` Aktion nach Commit; `U backend/app/modules/flow/service.py:838-893` Optimistic Locking). Pfade `U ...` sind relativ zu `upstream/STUPA-Workflow`.

Stand der Analyse: Branch `feat/m2-rollen` (M1 und M2 abgenommen), Arbeitsbaum ohne M3-Änderungen. Der Branch `feat/m3-pipeline` wird erst im letzten Schritt (nach Review) angelegt; bis dahin kein Commit, kein Push. Wo dieser Kontrakt dem PLAN oder M1/M2 widerspricht, gewinnt der Kontrakt, die Abweichung steht in Abschnitt 12. Was nicht belegt ist, steht als Vorschlag in Abschnitt 11 und wartet auf Luis. Die **fett** markierte Voreinstellung gilt, bis Luis anders entscheidet.

## 1. Lückenanalyse

Jede Zeile ist gegen den Code geprüft (Datei in Klammern), nicht gegen die Kontrakte.

### 1.1 Was schon existiert

| Teil | Stand | Beleg |
|---|---|---|
| Zustandsvokabular, alle acht `event_state`, `public_status` als Spalte samt CHECK | vorhanden, `public_status` wird nie geschrieben | `events/states.py`, `0002` |
| `TRANSITIONS` als Daten (T01, T02, T04, T05), reine `decide`-Funktion mit Reihenfolge Recht, Zustand, Guards | vorhanden | `pipeline/transitions.py` |
| Guards `has_field`, `date_in_future`, `image_or_exception`, `four_eyes` (Stub), `organization_scope_or_proposal` | vorhanden | `pipeline/guards.py` |
| `Reason` mit `code, field, severity, messageKey, fixAction`; `FixAction` hat nur `fill_field, change_date, upload_poster` | vorhanden, zu klein | `pipeline/reasons.py` |
| `PipelineService.guards` und `stage_fire` (ein Schreibweg auf `state`, `UPDATE ... WHERE state AND rev`, Revision, Status-Event, Audit, kein Commit) | vorhanden | `pipeline/service.py` |
| Aktionen nach dem Commit mit Schlüssel `event:<id>:rev:<n>:<action>` (Redis SET NX): `invalidate_feed_cache`, `ensure_derivatives` | vorhanden | `pipeline/actions.py` |
| Bildausnahme (`POST /image-exception`, Editor, Grund >= 10, nur `idea` bis `approved`) | vorhanden | `pipeline/exception.py` |
| Trigger `enforce_publish_image`, `keep_published_poster`, Append-only-Trigger auf `event_revision` und `event_status_event`, `events_app` ohne `DELETE` auf `event` | vorhanden | `0002` |
| `event.rev`, `public_seq` (nur bei T04 +1), optimistisches `rev` im PATCH-Body | vorhanden | `events/service.py` |
| `Actor`, `Snapshot`, `PosterSnapshot` (Guards lesen nie DB oder Session) | vorhanden | `pipeline/snapshot.py` |
| `EDITOR_FOUR_EYES` in `Settings` und `.env.*` (Standard `false`) | vorhanden, **nirgends gelesen** | `settings.py:164` |
| Permissions `event.cancel`, `event.edit_critical_live`, `event.assign_org`, `event.image_exception`, `event.approve` samt Rollenzuordnung | vorhanden, `cancel`, `edit_critical_live`, `assign_org` ungenutzt | `shared/permissions.py` |
| Test: Vollmatrix (T01/T02/T04/T05 × Zustand × Rolle × Poster × Zeit), Hypothesis-Zustandsmaschine "kein `approved`/`live` ohne Bild", Trigger-Tests, RBAC-Matrix | vorhanden, M1-Umfang | `tests/unit/pipeline/*`, `tests/integration/events/*` |
| `xfail(strict=True)`-Test "member liest eigenen Vorschlag" | wartet auf M3 | `test_visibility.py:46` |
| `coverage_critical.py` mit `pipeline` 100 % Branch | vorhanden | `scripts/coverage_critical.py` |
| Worker-Gerüst mit `WORKER_FUNCTIONS` und `cron_jobs` | vorhanden, nur Audit-Cron | `worker/main.py` |
| Frontend: Aufgaben (light), Dossier-Liste mit Statusfilter, I05 (nur mit Organisation), I07 (light), I13 und I15, `app-guard-list`, `app-poster-upload`, `app-status-text` | vorhanden, M1-Umfang | `frontend/src/app/features/**`, `shared/ui/**` |
| Kit: `app-tabs`, `app-segmented`, `app-dialog`, `app-filter-bar`, `app-config-diff`, `app-toast`; `@angular/cdk` 20 | vorhanden | `vendor/ui-kit`, `package.json` |

### 1.2 Was fehlt

| # | Lücke | Wirkung | Abschnitt |
|---|---|---|---|
| G1 | **Übergänge T03, T06, T07, T08, T08b, T09, T09b, T10, T11, T12** fehlen in `TRANSITIONS`; `TransitionName` ist `Literal["T01","T02","T04","T05"]` (Route, Schema, Frontend-Typ) | `followup`, `archived`, `withdrawn` sind unerreichbar | 2.2, 5 |
| G2 | **Aktionen** `cancel`, `postpone`, `reinstate`, `assign_organization`, `revert_revision` fehlen; `grant_image_exception` hat den falschen Pfad (`/image-exception` statt `/actions/image-exception`) | `public_status` bleibt immer `scheduled`; Vorschläge nicht zuweisbar; kein Zurücksetzen | 2.4, 5 |
| G3 | **Guards:** `venue_missing`, `rights_incomplete`, `attachment_quarantined`, `title_has_status`, `flyer_date`, `publish_at_not_reached`, `duplicate_unresolved`, `open_comment_on_hero`, `facts_invalid`, `checklist_open`, `location_unconfirmed`, `long_running`, `end_estimated`, `time_ambiguous`, `time_gap`, Nachbereitungs-Guards, Endezeit-Guard (`endedMoreThan`); `four_eyes` ist ein Stub, `EDITOR_FOUR_EYES` wird nicht gelesen | PLAN 4.4 nur zu 3 von 16 Tabellenzeilen umgesetzt (`image_required`, `start_in_past`, Feldprüfung) | 2.3 |
| G4 | **`FixAction` kennt 3 der 15 Werte**; die 12 übrigen Knöpfe des PLAN 4.4 fehlen | `app-guard-list` kann nur 3 Knöpfe | 2.3 |
| G5 | **Vier-Augen:** kein Wert `submitted_by` im Guard-Vergleich, kein CHECK an `event_status_event` (PLAN 3.3, E06), Spalten `four_eyes` und `submitted_by` fehlen dort | trusted Approver kann eigene Einreichung freigeben | 2.3, 7 |
| G6 | **`public_seq`** steigt nur bei T04; PLAN 3.5 verlangt +1 bei kritischer Änderung, Kurztext und `public_status` | ICS/Feed (M5) bekäme falsche `SEQUENCE` | 2.4, 3 |
| G7 | **Feldklassen E07 fehlen:** PATCH kennt nur "idea/planning ja, sonst 409". Keine Textkorrektur in `live`, keine Prüfenden-Korrektur in `in_review`, keine Link-Host-Regel, keine Liste "Nachträglich geändert", `CRITICAL_FIELDS` ohne Links; die Spalten `ticket_url`, `website_url`, `cost_text` existieren nicht | Kern des M3-Kriteriums "Kurztext in live ja, Uhrzeit nur über Redaktion" | 3, 7 |
| G8 | **Spalten fehlen:** `ticket_url`, `website_url`, `cost_text`, `publish_at`, `public_reason_code`, `public_reason_text`, `end_estimated`, `flyer_checked_at`, `text_reviewed_rev`, `published_rev`, `venue_id` (in M2 als D4 auf M3 verschoben) | Datenmodell | 7 |
| G9 | **Vorschläge (T00 ohne Organisation, E09):** `POST /events` verlangt `organizationId` und das Gate `event.create`; `_authorize_edit` weist `organization_id IS NULL` mit 403 ab; `visible_events_query` filtert NULL-Organisationen für alle außer `event.read_all` heraus; keine Quote | member kann nichts anlegen; `xfail` bleibt | 2.2, 5 |
| G10 | **Autosave (E21)** fehlt: keine `editor_draft`-Tabelle, kein `PUT .../draft`, kein `ETag`/`If-Match` (nur `rev` im Body), 409 liefert nicht die aktuelle Version | Datenverlust beim Tippen, kein Konfliktdialog | 4 |
| G11 | **Revisionen sind nicht lesbar:** kein `GET .../revisions`; `append_revision` kennt `field_class` nur als Parameter, die Klasse bei Zustandswechsel ist `state`, die Snapshot-Felder kennen die neuen Spalten nicht | Verlauf, Diff, Zurücksetzen unmöglich | 4, 5 |
| G12 | **Listen:** `GET /events` liefert `Page<EventOut>` (inklusive `descriptionMd`) ohne Board-Sicht, ohne Filter `category`, `mine`, `from`, `to`, ohne Blocker je Karte; `organizationId` statt Slug | I03 und I04 nicht baubar | 5 |
| G13 | **`GET /api/tasks`** fehlt | I02 nicht baubar | 5 |
| G14 | **`advance_states`** fehlt (T05 bei `publish_at`, T08, T08b, T09b); der Worker darf nur über `PipelineService` schreiben, `stage_fire` verlangt aber einen `Principal` | kein automatischer Übergang | 6 |
| G15 | **Feed:** `public_event_v` kennt `public_reason_*` und `venue_id` nicht; `PublicEventOut` kein Grund | Absage ohne öffentlichen Code; Ort aus `venue` fehlt | 7 |
| G16 | **Frontend:** kein Board (I03, `app-pipeline-board`), kein Handy-Tab/Sheet, keine Liste mit Filterchips und Kalender-Umschalter, I02 ohne Abschnitte, I05 ohne Vorschlagsweg, I07 ohne Feldklassen-Sperre, Autosave-Anzeige, 409-Dialog, "Nachträglich geändert", I13 ohne Pflichtnotiz-Satz T03/T06/T07/T10/T11 und ohne `publishAt`, kein I14; `NEXT` kennt nur T01/T02/T04/T05 | Abschnitt 8 | 8 |
| G17 | **Tests:** Vollmatrix deckt 4 von 14 Übergängen; keine Rolle `member`, `stupa`, `admin`, `system` in der Entscheidungsmatrix; keine U-GUARD-Suite; kein Autosave-/Feldklassen-/Worker-Test; kein axe-Lauf im Browser | Abschnitt 9 | 9 |
| G18 | **M2-Reste (Abnahme "Offen"):** nichts davon blockiert M3. Offen bleiben Authentik-`groups`-Claim (M8), MinIO-Service-Konto (Betrieb); die Zahlen 27/13 sind bestätigt | | 12 |

### 1.3 Was M3 nicht liefert (steht schon im PLAN bei M4 bis M7)

Kommentare mit Anker, Checklisten, `facts`-Profile, Mails und In-App-Inbox (M4); `format`, Nachbereitungsfelder (`retrospective_md`, `outcome`, `howto_verified_*`), Klonen (M5); Dubletten (M6); Serien/Angebote (M7). Die zugehörigen Guards laufen in M3 gegen einen **neutralen Snapshot-Wert** (Abschnitt 2.3, Spalte "M3"): die Guard-Funktion ist echt und getestet, die Datenquelle ist ein Platzhalter, der "erfüllt" meldet. So ändert M4 bis M6 nur die Befüllung des Snapshots, nie die Guard-Reihenfolge oder den Fehlercode.

## 2. Zustände, Übergänge, Aktionen, Guards (verbindliche Daten)

Diese Tabellen sind die Quelle von `pipeline/transitions.py`, des Frontends (Konstanten, die ein Test gegen die API-Antwort prüft) und der Orakel-Tabelle der Vollmatrix. Rollenkürzel wie PLAN 4.3: **Sb** `submitter`, **Or** `organizer`, **Ap** `approver` (nur trusted Org, sonst fällt er auf `organizer`, M2), **Ed** `editor`, **Sys** Worker, **M** jede angemeldete Person. `stupa`, `viewer` und `nobody` feuern nie. `admin` hat den Bypass von `Principal.has`, aber nie an den harten Guards vorbei (`image_required`, `four_eyes`) und nie an Sys-only-Übergängen.

### 2.1 Zustände

| Zustand | Label | Board-Spalte (Schlüssel) | `PATCH` kritisch | `PATCH` Text | Poster-Upload | in `public_event_v` |
|---|---|---|---|---|---|---|
| `idea` | Idee | Idee (`idea`) | Or, Ap, Ed; Sb eigene | wie kritisch | Or, Ap, Ed; Sb eigene | nein |
| `planning` | Planung | Planung (`planning`) | wie `idea` | wie `idea` | wie `idea` | nein |
| `in_review` | Freigabe angefragt | Freigabe (`in_review`) | 409 `field_locked` | nur `event.approve` (Tippfehler), Revision `text` | Ap, Ed | nein |
| `approved` | Freigegeben | Veröffentlicht (`published`) | 409 | 409 | 409 `field_locked` | nein |
| `live` | Veröffentlicht | Veröffentlicht (`published`) | `event.edit_critical_live` (Ap eigene Org, Ed), Guards laufen erneut | `event.edit` (Or, Ap, Ed); neuer Link-Host zählt kritisch | 409 (Abweichung 12.6) | ja |
| `followup` | Nachbereitung | Nachbereitung (`followup`) | 409 | 409 | 409 | ja |
| `archived` | Archiv | Filter "Archiv" | 409 | 409 | 409 | ja |
| `withdrawn` | Verworfen | Filter "Verworfen" | 409 | 409 | 409 | nein |

`public_status` (`scheduled | cancelled | postponed`) ist nur ab `live` änderbar (Aktionen 2.4) und steht nur dort im Feed. "Abgesagt" und "Verschoben" erscheinen als farbiger Text (`app-status-text`, Fehler- bzw. Warnfarbe), nie als Pille.

### 2.2 Übergänge T00 bis T12

`Notiz` = Pflichtnotiz: das Feld `note` des Requests muss nach `strip` 1 bis 500 Zeichen haben, sonst 422 `reason_required` (`errors[{field:"note"}]`). Die Notiz landet in `event_status_event.note` und **nie** im Feed.

| Id | Von nach | Wer | Recht (`Principal.has`, Org des Dossiers) | Guards in Auswertungsreihenfolge (Abschnitt 2.3) | Setzt (im selben `UPDATE`) | Notiz | Nach dem Commit (M3) |
|---|---|---|---|---|---|---|---|
| T00 | (neu) nach `idea` | M (Vorschlag), Sb, Or, Ap, Ed | mit `organizationId`: `event.create` in der Org (sonst 404); ohne: nur Session | `organizationScopeOrProposal`, `proposalQuota(5)`; Schema: `title`, `startsAt` Pflicht | `created_by`; ohne `endsAt`: `ends_at = starts_at + 2 h`, `end_estimated = true` | nein | Revision 1, Status-Event T00, Audit; Mail an die Redaktion bei Vorschlag: M4 |
| T01 | `idea` nach `planning` | Sb (eigene), Or, Ap, Ed | `event.edit`; Sb nur `created_by = sub` | `hasField(title, starts_at, organization_id)` | | nein | Checkliste aus Vorlage, Bibliotheksvorschläge: M4 |
| T02 | `planning` nach `in_review` | Or, Ap, Ed | `event.submit` | `hasField(title, summary, starts_at, ends_at, primary_category_id)`, `venueOrText`, `dateInFuture`, `checklistDone(planning)`, `factsValid`; Warnungen `end_estimated`, `long_running`, `time_ambiguous`, `time_gap` | `submitted_by = Actor.sub` | nein | Aufgabe und Mail an Prüfende: M4 |
| T03 | `in_review` nach `planning` | Ap, Ed | `event.approve` | `openCommentRequired` (M3: die Notiz ist die Rückfrage) | `submitted_by = NULL`, `approved_by = NULL` | **ja** | Mail an Organisator:innen: M4 |
| T04 | `in_review` nach `approved` | Ap (eigene trusted Org), Ed | `event.approve` | `fourEyes` (403, vor allen anderen), dann `dateInFuture`, `imageOrException`, `rightsComplete`, `attachmentsScanned`, `noOpenDuplicate`, `titleClean`, `flyerDateConfirmed`, `noOpenCommentOnField(hero)`, `locationConfirmed`; Warnung `long_running` | `slug`, `public_seq + 1`, `approved_by = Actor.sub`, `publish_at` (Body `publishAt`, leer = `NULL`) | nein | `ensure_derivatives`; Slug nie wieder geändert |
| T05 | `approved` nach `live` | Ap, Ed, Sys | `event.approve`; Sys: nur über `advance_states` | `publishAtReached` (blockt nur Sys), `imageOrException`, `rightsComplete`, `attachmentsScanned`, `titleClean`, `flyerDateConfirmed`, `noOpenDuplicate`, `noOpenCommentOnField(hero)`; nur Sys zusätzlich `dateInFuture`, `humanApproval` | `published_rev = neue rev` | nein | `invalidate_feed_cache` |
| T06 | `approved` nach `in_review` | Ap, Ed | `event.approve` | | `approved_by = NULL`, `publish_at = NULL` | **ja** | |
| T07 | `live` nach `approved` | Ap, Ed | `event.approve` | | `public_seq + 1`, `published_rev = NULL`, `publish_at = NULL` | **ja** | `invalidate_feed_cache` (öffentlich 404/410 auf `/e/<slug>`: Stufe B) |
| T08 | `live` nach `followup` | Sys | | `endedMoreThan(12h)`, `origin_kind IN (internal, mcp)` | `published_rev = NULL` | nein | Erinnerung "Nachbereitung" nach 7 Tagen: M4 |
| T08b | `live` nach `archived` | Sys | | `endedMoreThan(12h)`, `origin_kind IN (imported, legacy)` | `published_rev = NULL` | nein | |
| T09 | `followup` nach `archived` | Or, Ap, Ed | `event.submit` | `retrospectiveFilled`, `outcomeSetOrWaived`, `checklistDone(followup)`, `howtoVerified` | | nein | `format.last_verified_at`: M5 |
| T09b | `followup` nach `archived` | Sys | | `followupOlderThan(30d)` | | nein | Kennzeichen "Anleitung ungeprüft", Mail: M5 |
| T10 | `archived` nach `followup` | Ed | `event.restore` (neu, D2) | | | **ja** | |
| T11 | `idea`, `planning`, `in_review`, `approved` nach `withdrawn` | Sb (eigene `idea`), Or, Ap, Ed, M (eigener Vorschlag) | `event.cancel`; Sb: `event.edit` und `created_by = sub` und Zustand `idea`; M: `organization_id IS NULL` und `created_by = sub` | | | **ja** | |
| T12 | `withdrawn` nach `idea` | Ed | `event.restore` | | `submitted_by = NULL`, `approved_by = NULL`, `publish_at = NULL` | nein | |

Regeln für alle Übergänge:

1. **Auswertungsreihenfolge** von `decide`: Recht (`forbidden`, 403), Zustand (`invalid_transition`, 409), Pflichtnotiz (422 `reason_required`), **`fourEyes` (403 `four_eyes`)**, übrige Guards (`blocked`, 422 mit dem Code des ersten Blockers). Das Recht steht vor dem Zustand (M1).
2. **Sys-only** (T08, T08b, T09b): `permission = None`. Ein Mensch, auch `admin`, bekommt 403 `forbidden`; der Pfadparameter akzeptiert alle 14 Ids (`Literal` aus `TRANSITIONS`).
3. **`public_seq`** steigt in T04, T07 und in den Aktionen `cancel`, `postpone`, `reinstate`; außerdem bei einer Änderung in `live`, die ein kritisches Feld oder `summary` berührt (Abschnitt 3). T05 und T08 ändern ihn nicht (M1-Verhalten, PLAN 3.5).
4. **Revision je Übergang:** `field_class = state`, `change_note = note`. Status-Event je Übergang mit `four_eyes` und `submitted_by` (Abschnitt 2.5).
5. **Idempotenz:** Übergang mit `If-Match` (optional; Pflicht bei T04 und T05, 12.23): weicht die ETag von `event.rev` ab, 409 `conflict` mit der aktuellen Version (I13: "Ein anderer Übergang war schneller."). Ohne `If-Match` sichert `UPDATE ... WHERE state = :from AND rev = :rev` (M1).
6. **`publishAt`** (nur T04, `AwareDatetime`): muss in der Zukunft liegen (422 `publish_at_in_past`) und vor `ends_at` (422 `publish_after_end`). Für jeden anderen Übergang mit `publishAt`: 422 `validation_error`.
7. **Aktion nach dem Commit** wie M1: Schlüssel `event:<id>:rev:<n>:<action>`, Fehler werden geloggt und nie zurückgerollt. M3 registriert nur `invalidate_feed_cache` und `ensure_derivatives`; Mail-Aktionen kommen mit M4 und stehen hier nur als Absicht.

### 2.3 Guards (`pipeline/guards/`) und Reihenfolge der `reasons[]`

Jeder Guard ist eine reine Funktion `(snapshot, actor, now) -> list[Reason]`. Die Liste in `reasons[]` folgt der Reihenfolge dieser Tabelle (Blocker vor Warnungen ist Sache der UI). Spalte **M3** nennt die Datenquelle: *echt* = aus den Zeilen des Dossiers, *Platzhalter* = der Snapshot trägt einen neutralen Wert, die Guard-Funktion ist implementiert und mit Unit-Tests belegt (U-GUARD), der Wert wird erst von dem genannten Meilenstein befüllt.

| # | Code | Guard (PLAN) | Prüft | Schwere | `fixAction` | Übergänge | M3 |
|---|---|---|---|---|---|---|---|
| 1 | `field_missing` | `hasField(...)` (Varianten: T01 `{title, starts_at, organization_id}`; T02 `{title, summary, starts_at, ends_at, primary_category_id}`; Reason mit `field` = camelCase-Name) | Feld nicht leer (Strings nach `strip`) | blocker | `fill_field` | T01, T02 | echt |
| 2 | `venue_missing` | `venueOrText` | weder `venue_id` noch nicht-leerer `venue_text` | blocker | `pick_venue` | T02 | echt (ersetzt M1: `field_missing` mit `field=venueText`) |
| 3 | `start_in_past` | `dateInFuture` | `ends_at > now` (laufendes Event besteht) | blocker | `change_date` | T02, T04, Sys-T05, `reinstate` | echt |
| 4 | `image_required` | `imageOrException` | Poster `clean` + Derivate + `alt_text` + `credit` + `rights_basis <> unknown`, oder gültige Ausnahme (Grund >= 10) | blocker | `upload_poster` | T04, T05, `reinstate`, Änderung in `live` | echt (M1 unverändert, gleich streng wie der Trigger) |
| 5 | `rights_incomplete` | `rightsComplete` | `persons_depicted` ohne nicht-leere `consent_note` (nur wenn ein Poster zählt, nicht bei gültiger Ausnahme) | blocker | `fill_rights` | T04, T05, `reinstate` | echt; `attachment_poster_ok` (SQL) erhält dieselbe Bedingung (Netz) |
| 6 | `attachment_quarantined` | `attachmentsScanned` | ein nicht ausgeblendetes Anhangsobjekt des Dossiers neben dem Poster hat `scan_status <> clean` | blocker | (keine, wartet) | T04, T05 | echt, in M3 ohne Wirkung (außer Poster gibt es keine weitere Anhangsart; M4 aktiviert es) |
| 7 | `duplicate_unresolved` | `noOpenDuplicate` | `snapshot.duplicate_score >= 0,8` und nicht aufgelöst | blocker | `review_duplicate` | T04, T05 | Platzhalter `None` (M6) |
| 8 | `title_has_status` | `titleClean` | Titel passt auf `\[(canceled|cancelled|abgesagt|verschoben)\]` oder `!verschoben!` oder das Wort `abgesagt` (case-insensitive) **und** `public_status = scheduled` | blocker | `mark_cancellation` | T04, T05, `reinstate` | echt |
| 9 | `open_comment_on_hero` | `noOpenCommentOnField(hero)` | `snapshot.open_hero_comments > 0` | blocker | `open_comment` | T04, T05 | Platzhalter `0` (M4) |
| 10 | `flyer_date` | `flyerDateConfirmed` | `sha256` des Posters hängt an einem anderen Dossier (nicht ausgeblendet) mit anderem lokalen Startjahr; erfüllt, wenn `flyer_checked_at >= poster.created_at`. Serien gibt es erst in M7, also zählt jede Fremdnutzung | blocker | `confirm_flyer` | T04, T05, `reinstate` | echt (Abfrage im Service, `PosterSnapshot.reused_in_other_year`) |
| 11 | `location_unconfirmed` | `locationConfirmed` | `location_precision` gesetzt und bestätigt | blocker | `confirm_location` | T04 | Platzhalter erfüllt (Spalte kommt mit M5, M1-Abweichung 4) |
| 12 | `facts_invalid` | `factsValid` | Profil der Hauptkategorie vollständig, z. B. Party ohne `age_limit` | blocker | `fill_facts` | T02 | Platzhalter `None` (M4, `facts`) |
| 13 | `checklist_open` | `checklistDone(planning)` bzw. `(followup)` | Pflichtpunkte der Phase offen | blocker | `open_checklist` | T02, T09 | Platzhalter `0` (M4) |
| 14 | `open_comment_required` | `openCommentRequired` | mindestens ein offener Kommentar | blocker | `open_comment` | T03 | in M3 **entfällt die Prüfung**; die Pflichtnotiz (2.2) ersetzt sie. Der Guard ist ein Platzhalter, der "erfüllt" meldet; M4 schaltet ihn scharf |
| 15 | `publish_at_not_reached` | `publishAtReached` | `publish_at IS NOT NULL AND publish_at <= now`; **nur Sys**. Ein Mensch darf früher veröffentlichen | blocker | (keine) | Sys-T05 | echt |
| 16 | `not_human_approved` | `humanApproval` | `approved_by` gesetzt und nicht mit `system:` beginnend; nur Sys | blocker | (keine) | Sys-T05 | echt |
| 17 | `not_ended_yet` | `endedMoreThan(12h)` | `ends_at + 12 h <= now` | blocker | (keine) | T08, T08b | echt |
| 18 | `origin_kind_mismatch` | `originIs(...)` | T08: `internal | mcp`; T08b: `imported | legacy` | blocker | (keine) | T08, T08b | echt |
| 19 | `retrospective_missing` | `retrospectiveFilled` | `retrospective_md` nicht leer | blocker | (keine) | T09 | Platzhalter erfüllt (M5) |
| 20 | `outcome_missing` | `outcomeSetOrWaived` | `outcome` gesetzt oder bewusst verzichtet | blocker | (keine) | T09 | Platzhalter erfüllt (M5) |
| 21 | `howto_unverified` | `howtoVerified` | `howto_verified_at` gesetzt | blocker | (keine) | T09 | Platzhalter erfüllt (M5) |
| 22 | `followup_not_due` | `followupOlderThan(30d)` | letztes Status-Event mit `to_state = followup` ist >= 30 Tage her | blocker | (keine) | T09b | echt |
| 23 | `four_eyes` | `fourEyes` | s. 2.5; bindet die freigebende Person an eine andere als `submitted_by` | blocker (403) | (keine; "andere Person") | T04 (T05 nicht, D11) | echt |
| 24 | `time_ambiguous`, `time_gap` | `wallClockOk` | Wandzeit 25.10. 02:30 bzw. 28.03. 02:30 | warning | `confirm_time` | T02, T04 | Platzhalter leer (M6, Zeitzonen-Matrix) |
| 25 | `end_estimated` | | `end_estimated = true` (Ende fehlte, Start + 2 h) | warning | `set_end` | T02, T04 | echt |
| 26 | `long_running` | | `ends_at - starts_at > 7 Tage` | warning | `make_offer` | T02, T04 | echt |

Weitere Fehlercodes ohne `reasons[]`-Eintrag: `reason_required` (422), `proposal_quota_exceeded` (422, Guard `proposalQuota`), `organization_scope` (404 nach außen), `invalid_transition` (409), `forbidden` (403).

`FixAction` wird additiv um `pick_venue, fill_rights, review_duplicate, mark_cancellation, open_comment, confirm_flyer, confirm_location, fill_facts, open_checklist, confirm_time, set_end, make_offer` erweitert (insgesamt 15 Werte, PLAN 4.4 Spalte "Knopf"). `messageKey = guards.<code>`, jedes neue `guards.<code>` und `fix.<fixAction>` bekommt einen deutschen Text (Abschnitt 8.10). Eine unbekannte `fixAction` darf das Frontend nie abstürzen lassen (Knopf entfällt).

### 2.4 Aktionen neben den Zuständen

Eigene Endpunkte (Abschnitt 5.4), alle mit Pflichtgrund `reason` (1 bis 500 Zeichen nach `strip`, sonst 422 `reason_required`), Audit, Revision und Status-Event (`transition_id` = Aktionsname, `from_state = to_state = state`, `note = reason`). Der Grund steht **nur** im Status-Event, nie im Audit-`data` und nie öffentlich (E08, A05).

| Aktion | Wer | Recht | Zustand | `public_status` danach | Wirkung | Guards | Audit |
|---|---|---|---|---|---|---|---|
| `cancel` | Or, Ap, Ed | `event.cancel` | `live` | `cancelled` (von `scheduled`, `postponed`) | `public_seq + 1`, `public_reason_code`, `public_reason_text` (Text nur mit `event.approve`) | | `EVENT_CANCEL` |
| `postpone` | Or, Ap, Ed | `event.cancel`; mit `newStartsAt` zusätzlich `event.edit_critical_live` | `live` | `postponed` (von `scheduled`) | `public_seq + 1`; mit neuem Termin werden `starts_at`/`ends_at` geändert (Revision `critical`), Status bleibt `postponed` bis `reinstate` (D9) | neuer Termin: `ends_at > now` (422 `start_in_past`), `endsAt >= startsAt` | `EVENT_POSTPONE` |
| `reinstate` | Ap, Ed | `event.approve` | `live` | `scheduled` (von `cancelled`, `postponed`) | `public_seq + 1`, `public_reason_*` zurück auf `none`/`NULL` | `dateInFuture`, `imageOrException`, `rightsComplete`, `titleClean`, `flyerDateConfirmed` | `EVENT_REINSTATE` |
| `grant_image_exception` (`image-exception`) | Ed | `event.image_exception` | `idea`, `planning`, `in_review`, `approved` | | `image_exception = {granted_by, reason, at}`; Grund >= 10 Zeichen; gilt nur für diese Event-ID; wird nie geklont | | `EVENT_IMAGE_EXCEPTION` (M1) |
| `assign_organization` (`assign-organization`) | Ed | `event.assign_org` | `organization_id IS NULL` (Vorschlag in `idea`, oder `withdrawn`) | | setzt `organization_id` (aktive Org, sonst 404); danach liest die vorschlagende Person das Dossier nicht mehr (D7) | | `EVENT_ASSIGN_ORG` |
| `revert_revision` (`revert-revision`) | Ap, Ed | `event.edit_critical_live` | `idea`, `planning`, `live` (in `in_review` und `approved` 409 `field_locked`, 12.22) | | neue Revision mit den Inhaltsfeldern von Revision `rev` (Abschnitt 4.4); nie Zustand, Slug, Organisation, Poster | in `live` die Live-Guards (3.4) auf dem Ergebnis | `EVENT_REVERT` |
| `acknowledge_changes` (`acknowledge-changes`) | Ap, Ed | `event.edit_critical_live` | `live` | | `text_reviewed_rev = rev`; entfernt den Eintrag aus "Nachträglich geändert" (D13) | | `EVENT_ACK_CHANGES` |
| `confirm_flyer` (`confirm-flyer`) | Or, Ap, Ed (Sb eigene) | `event.edit` | `idea` bis `in_review` | | `flyer_checked_at = now` (D13) | | `EVENT_FLYER_CONFIRM` |

`public_reason_code` ∈ `none | room | speaker | illness | registration | weather | other` (Liste fest, PLAN 3.3). `public_reason_text` höchstens 140 Zeichen ohne Steuerzeichen. Ein Ausfall des Postings an Abonnent:innen gehört zu M4/B.

### 2.5 Vier-Augen und `Actor`

`Actor` wird um zwei Felder erweitert: `kind ∈ org | editor | admin | system` und `four_eyes: bool` (bindet diese Person am Guard `fourEyes`). `actor_of(principal, org_id, editor_four_eyes)` leitet beides ab, ohne `principal.roles`: `kind = editor`, wenn `"event.approve"` in `principal.permissions` (globales Recht); sonst `admin`, wenn `principal.is_admin`; sonst `org`. `four_eyes = kind in (org, admin) or (kind == editor and settings.editor_four_eyes)`. Der Worker bekommt `SYSTEM_ACTOR = Actor("system:advance_states", permissions=frozenset(), kind="system", four_eyes=False)`.

`fourEyes` blockt, wenn `actor.four_eyes` und (`snapshot.submitted_by is None` oder `snapshot.submitted_by == actor.sub`). `submitted_by is None` blockt, damit ein Import-Weg ohne Einreichende (M6) nicht an der Prüfung vorbeiläuft. Antwort: **403** mit `code=four_eyes` und `reasons[]` (D1). Die Redaktion ohne `EDITOR_FOUR_EYES` gibt eigene Einreichungen frei; **jede** solche Selbstfreigabe schreibt `audit_entry.data.selfApproved = true` (E06) und zählt in der Statusseite (M8).

**DB-Netz (E06, PLAN 3.3):** `event_status_event` bekommt `four_eyes boolean NOT NULL DEFAULT false` und `submitted_by text`; `stage_fire` füllt beide aus dem Actor und dem Snapshot. CHECK `ck_event_status_event_four_eyes`: `transition_id <> 'T04' OR NOT four_eyes OR (submitted_by IS NOT NULL AND actor_id IS DISTINCT FROM submitted_by)`. Die Zeile entsteht in derselben Transaktion wie das `UPDATE`; scheitert der CHECK, rollt alles zurück und `stage_fire` übersetzt SQLSTATE `23514` mit diesem Constraint-Namen in dasselbe 403 `four_eyes` (analog zum Bild-Trigger, M1). Die Spaltennamen weichen vom PLAN ab (`via_org_role`, Abweichung 12.3).

## 3. Feldklassen (E07)

Reine Funktion `pipeline/fieldclass.py: plan_patch(snapshot, actor, changes) -> PatchPlan` (Besitzer `pipeline`, damit die 100-%-Branch-Pflicht greift). Sie kennt weder DB noch Session; `EventService.patch` ruft sie und führt den Plan aus.

### 3.1 Klassen

| Klasse | Felder (API-Namen) | Anmerkung |
|---|---|---|
| **kritisch** | `title`, `startsAt`, `endsAt`, `allDay`, `venueId`, `venueText`, `primaryCategoryId`, `ticketUrl`, `websiteUrl`, das Poster (`hero_attachment_id`), und jeder **neue Link-Host in Textfeldern** (3.3) | in `live` nur mit `event.edit_critical_live`, `public_seq + 1`, Live-Guards (3.4) |
| **Text** | `summary`, `descriptionMd`, `costText` | in `live` direkt durch `event.edit` mit Revision `text`; `public_seq + 1` nur bei `summary` (PLAN 3.5: "Kurztext") |
| Zustand | `state`, `publicStatus`, `publicReason*`, `publishAt`, `slug`, `submittedBy`, `approvedBy` | nie über `PATCH`; Schreibweg sind Übergänge und Aktionen (2) |

`PATCH` kennt die Felder `title, startsAt, endsAt, allDay (weiter 422), venueId, venueText, primaryCategoryId, ticketUrl, websiteUrl, summary, descriptionMd, costText` plus `note` (Änderungsnotiz, <= 500, landet in `event_revision.change_note`). `ticketUrl` und `websiteUrl`: `https://`, <= 500 Zeichen, kein Benutzerteil (`user@`), Host mit Punkt, keine Steuerzeichen, sonst 422 (Frontend: "Ticket-Link muss mit https:// beginnen."). `venueId` verweist auf einen aktiven Ort (sonst 422 `unknown_venue`); `venueText` bleibt als Freitext-Alternative. `costText` <= 200 Zeichen. `null` löscht ein optionales Feld, `title`, `startsAt`, `endsAt` nie (422).

### 3.2 Wer darf was (Entscheidungstabelle von `plan_patch`)

Vorab, unverändert aus M1: ohne `event.edit` in der Org des Dossiers 403 (`forbidden`); ein `submitter` an einem fremden Dossier derselben Org 403. Danach die Sperre nach Zustand und Klasse:

| Zustand | kritische Änderung | Textänderung |
|---|---|---|
| `idea`, `planning` | erlaubt | erlaubt |
| `in_review` | 409 `field_locked` | erlaubt nur mit `event.approve` (Prüfende korrigieren Tippfehler), sonst 409 |
| `approved`, `followup`, `archived`, `withdrawn` | 409 `field_locked` | 409 `field_locked` |
| `live` | erlaubt nur mit `event.edit_critical_live`, sonst 409 `field_locked` | erlaubt; Sb bleibt ausgeschlossen (403, weil `submitter` nur `idea`/`planning` bearbeitet) |

Eine Anfrage mit gemischten Feldern ist **alles oder nichts**: sperrt auch nur ein Feld, 409 `field_locked` mit `errors[{field, msg}]` je gesperrtem Feld, nichts wird gespeichert. Ein Dossier ohne Organisation (Vorschlag) bearbeitet nur, wer `event.edit` **global** hält (Ed, Admin); die vorschlagende Person kann nur zurückziehen (T11).

`EventOut` trägt zwei Hilfsfelder nur für die UX: `editableFields: string[]` (die Felder, die der Aufrufer jetzt per `PATCH` ändern dürfte, berechnet mit derselben Funktion) und `lockReason: null | "in_review" | "approved" | "live_critical" | "closed"`. Der Server entscheidet weiter bei jedem Schreibzugriff.

### 3.3 Link-Hosts in Texten

`link_hosts(text) -> frozenset[str]` findet `https?://<host>` und `www.<host>` in `summary`, `descriptionMd`, `costText`, normalisiert den Host (klein, ohne Port, IDNA nach ASCII) und ignoriert `mailto:`. Eine Textänderung ist **kritisch**, wenn die neue Host-Menge einen Host enthält, der in `hosts(alte summary, alte descriptionMd, alte costText, alter ticketUrl, alter websiteUrl)` nicht vorkommt (A04). Dann gilt 3.2 "kritisch". Revision, `field_class` und `public_seq` folgen der kritischen Klasse.

### 3.4 Live-Guards

Nach einer kritischen Änderung in `live` (und bei `revert_revision`, `reinstate`) laufen auf dem **Ergebnis-Snapshot**: `hasField` der T02-Menge, `venueOrText`, `imageOrException`, `rightsComplete`, `attachmentsScanned`, `titleClean`, `flyerDateConfirmed`. Nicht: `dateInFuture` (eine laufende Veranstaltung darf nachträglich korrigiert werden), `publishAtReached`, `fourEyes`. Ein Blocker ergibt 422 mit `reasons[]` wie bei einem Übergang; gespeichert wird dann nichts.

### 3.5 Revisionsklasse und `public_seq`

`field_class` der neuen Revision: `critical`, sobald ein kritisches Feld oder ein neuer Host beteiligt ist, sonst `text`. `public_seq + 1` im selben `UPDATE`, wenn der Zustand `live` ist und (Klasse `critical` oder `summary` geändert). Danach `invalidate_feed_cache`. In `idea`, `planning`, `in_review` ändert sich `public_seq` nie.

### 3.6 Liste "Nachträglich geändert"

`baselineRev = max(event.published_rev, event.text_reviewed_rev)`. Ein Dossier gehört in die Liste, wenn sein Zustand `live` ist und es eine Revision mit `field_class = text`, `rev > baselineRev` und `actor_id <> Aufrufer` gibt. Sichtbar für Personen mit `event.edit_critical_live` (Ap in der eigenen Org, Ed). "Zurücksetzen" ist `revert_revision` mit `rev = baselineRev`; "Gesehen" ist `acknowledge_changes`. Ein Eintrag verschwindet, wenn das Dossier `live` verlässt.

## 4. Revisionen, ETag und Autosave (E21)

### 4.1 Revisionen

`event_revision` bleibt append-only (Trigger, kein `DELETE`/`UPDATE`). **Eine Revision entsteht nur bei ausdrücklichem Speichern (`PATCH`), bei einem Übergang, bei einer Aktion und bei `revert_revision`**, nie beim Autosave. `rev` steigt mit jeder solchen Revision um 1. Der Snapshot (`_SNAPSHOT_FIELDS`) wächst um `venue_id, ticket_url, website_url, cost_text, publish_at, public_reason_code, public_reason_text, end_estimated, flyer_checked_at, text_reviewed_rev, published_rev`; ältere Zeilen ohne diese Schlüssel werden mit `.get` gelesen. `actor_type`: `human` für Personen, `system` für den Worker (`actor_id = "system:advance_states"`), `agent` ab Stufe D. `field_class`: `state` (Übergang, Aktion ohne Inhalt, Anlage), `critical`, `text`, `dossier` (Bildausnahme, Organisationszuweisung, `acknowledge_changes`, `confirm_flyer`).

### 4.2 ETag und `If-Match`

Jede Antwort mit einem `EventOut` (`GET`, `PATCH`, Übergang, Aktion, `POST`) trägt `ETag: "<rev>"` (stark). `PATCH` und `PUT .../draft` verlangen die Version als **`If-Match`-Header**. Fehlt er, gilt ersatzweise `rev` im Body (M1-Kompatibilität); fehlen beide, antwortet der Server **428** `precondition_required`; stehen beide da und sind verschieden, 422 `validation_error`. Eine veraltete Version ergibt **409 `conflict`** als Problem+JSON mit Erweiterung `current` (das aktuelle `EventOut`, nur wenn der Aufrufer das Dossier liest, sonst 404 wie immer) und `currentRev`. Übergänge und Aktionen nehmen `If-Match` optional (2.2 Regel 5).

### 4.3 Autosave

- **Tabelle `editor_draft`** (E21, Migration 0004): `owner_kind text CHECK (owner_kind IN ('event'))`, `owner_id uuid`, `principal_sub text`, `base_rev integer`, `fields jsonb`, `updated_at timestamptz`, `PRIMARY KEY (owner_kind, owner_id, principal_sub)`. Eine Zeile je Person und Dossier, wird überschrieben. Kein Fremdschlüssel (M4 hängt `document` an dieselbe Tabelle). `events_app` bekommt `DELETE` (Zeile in `roles.sql`, Stufe 2).
- **`PUT /api/events/{id}/draft`** (`If-Match` = `base_rev`, Body `{fields}`, <= 64 KiB, Teilmenge der `PATCH`-Felder, `extra=forbid`): schreibt oder überschreibt die eigene Zeile. Prüfungen **ohne Wirkung auf das Dossier**: Lesen (404), `event.edit` (403), `plan_patch` auf `fields`: ein in diesem Zustand für diese Person gesperrtes Feld ergibt 409 `field_locked` (in `live` also **kein Autosave auf kritische Felder**), `If-Match <> event.rev` ergibt 409 `conflict` mit `current`. Antwort 200 `{baseRev, fields, updatedAt}`. Erzeugt weder Revision noch `public_seq` noch Cache-Neubau noch Audit (A03).
- **`GET /api/events/{id}/draft`**: die eigene Zeile oder 204. Sie kann ein `baseRev` unter `event.rev` haben; das Frontend zeigt dann die Dreiwege-Ansicht (Basis aus `GET .../revisions/{baseRev}`, "Deins" aus dem Entwurf, "Neu" aus `current`).
- **`DELETE /api/events/{id}/draft`**: verwirft die eigene Zeile (204).
- **Wirksam wird der Entwurf** durch `PATCH` (Speichern, Verlassen, Übergang): der Client sendet vor einem Übergang erst `PATCH` mit den Entwurfsfeldern, dann den Übergang. Ein erfolgreiches `PATCH` löscht die Zeile des Aufrufers in derselben Transaktion. In `in_review` und `live` nur durch ausdrückliches "Speichern" (nie halb getippter Text öffentlich). **Nach 30 Minuten Ruhe** wendet der **Client** den Entwurf an (Abweichung 12.7); der Server hält Entwürfe bis dahin und löscht Zeilen, die älter als 14 Tage sind (Worker `purge_drafts`, täglich 03:30 UTC).
- **Datenschutz:** der Entwurf gehört der Person; keine andere Rolle liest ihn, auch nicht `admin`.

### 4.4 `revert_revision`: was zurückkommt

Zurückgesetzt werden die **Inhaltsfelder** `title, summary, description_md, starts_at, ends_at, venue_id, venue_text, primary_category_id, ticket_url, website_url, cost_text` aus dem Snapshot der Ziel-Revision, als **neue Revision** (`change_note = "Zurückgesetzt auf Revision N"`, `field_class` nach 3.5). Nie zurück: `state`, `public_status`, `slug`, `organization_id`, `image_exception`, `submitted_by`, `approved_by`, Zähler. Unterscheidet sich `hero_attachment_id` des Snapshots von dem des Dossiers, 409 `revert_poster_replaced` ("Zurücksetzen nicht möglich: das Poster der alten Fassung wurde ersetzt."). Eine Ziel-Revision, die es nicht gibt oder die einem anderen Dossier gehört: 404.

## 5. API-Vertrag M3

Alle Pfade unter `/api`. Konventionen wie M1 und M2: camelCase (`CamelModel`, `extra="forbid"`), Zeiten ISO-8601 mit Offset, Fehler ausnahmslos `application/problem+json`, zustandsändernde Routen mit CSRF, der Router committet, Audit in derselben Transaktion. **Gate-Regel (M2) mit zwei Ausnahmen:** `POST /events` und `POST /events/{id}/transitions/{T}` haben als Gate nur die Session (`library.read`), weil Vorschläge und das Zurückziehen eigener Vorschläge der Rolle `member` gehören (PLAN 5.2); die Entscheidung trifft der Service mit `Principal.has(perm, org_id)`. Bei allen anderen Routen gilt weiter: fehlendes Routenrecht 403 unabhängig von der Objekt-ID, 404 erst danach.

### 5.1 Typen

```
EventOut      (M1) + { venueId|null, venue: VenueRef|null, costText|null, ticketUrl|null, websiteUrl|null,
                       publishAt|null, publicReason: { code, text|null }|null,   # null bei scheduled
                       endEstimated, textReviewedRev, publishedRev|null, flyerCheckedAt|null,
                       allowedTransitions: TransitionId[],                       # jetzt alle 14 Ids
                       allowedActions: ActionName[], editableFields: string[],
                       lockReason: null|"in_review"|"approved"|"live_critical"|"closed" }
EventCard     { id, title, state, publicStatus, startsAt, endsAt, tzid, organization: OrgRef|null,
                venueLabel|null, primaryCategory: CategoryRef|null, publishAt|null, hasPoster,
                createdBy: { sub, displayName|null }, rev,
                allowedTransitions[], nextTransition|null,
                blockers: ReasonOut[] (höchstens 3 Blocker von nextTransition, nur wenn nextTransition erlaubt ist),
                blockerCount, moves: { <columnKey>: TransitionId }, openQuestions: 0 }   # openQuestions: M4
BoardColumn   { key: idea|planning|in_review|published|followup|archived|withdrawn, states[], total,
                items: EventCard[], truncated }
BoardOut      { columns: BoardColumn[], generatedAt }
TransitionId  T01|T02|T03|T04|T05|T06|T07|T08|T08b|T09|T09b|T10|T11|T12
ActionName    cancel|postpone|reinstate|image-exception|assign-organization|revert-revision|
              acknowledge-changes|confirm-flyer
TransitionIn  { note?: str<=500, publishAt?: AwareDatetime }          # publishAt nur T04
RevisionOut   { rev, at, actor: { sub, displayName|null }, actorType, fieldClass, changeNote|null,
                changedFields: string[] }                              # Felder gegenüber der Vorgängerrevision
RevisionDetail RevisionOut + { snapshot: object }                      # camelCase-Schlüssel
DraftOut      { baseRev, fields: object, updatedAt }
```

`moves` einer Karte: für jede Board-Spalte, die die Karte per Drag erreichen darf, die Übergangs-Id. Der Server berechnet sie aus `allowedTransitions` und dieser Tabelle (Quelle `BOARD_MOVES` in `events/board.py`, Test gegen `TRANSITIONS`): `idea` → `planning`: T01; `planning` → `in_review`: T02; `in_review` → `planning`: T03, → `published`: T04; `approved` → `in_review`: T06. Alle anderen Übergänge (T05, T07, T09, T11 ...) laufen über das Kartenmenü bzw. I07, nie über Drag.

### 5.2 Dossiers

| Methode Pfad | Gate | Request | Antwort / Fehler |
|---|---|---|---|
| `GET /events` | `library.read` | Query `view=list\|board` (Standard `list`), `state` (wiederholbar), `organization` (Slug), `category` (Slug der Haupt- oder Elternkategorie), `mine=1` (`created_by` oder `submitted_by` ist der Aufrufer), `q` (Titel/Kurztext, `ilike`, <= 200), `from`, `to` (lokale Daten `YYYY-MM-DD`, `starts_at` in `Europe/Berlin`), `sort` (`startsAt` Standard, `-startsAt`), `limit` (1..200, 50), `offset`; `view=board`: `columnLimit` (1..100, 50) statt `limit/offset` | `view=list`: `Page<EventCard>`; `view=board`: `BoardOut` (Spalten `idea, planning, in_review, published, followup`; `state=archived` oder `withdrawn` liefert genau diese eine Spalte). Gefiltert in SQL nach `readable_org_ids` **plus** eigene Vorschläge (5.5 Sichtbarkeit). Unbekannter Slug: leere Antwort. Spalten `idea`-`published` aufsteigend nach `startsAt`, `followup`, `archived`, `withdrawn` absteigend |
| `POST /events` | `library.read` | `EventCreate`: wie M1, aber `organizationId` optional, `endsAt` optional (fehlt es: `startsAt + 2 h`, `endEstimated = true`), neu `venueId?`, `costText?`, `ticketUrl?`, `websiteUrl?` | 201 `EventOut` (`ETag`). Mit `organizationId`: `event.create` in der Org, sonst 404. Ohne: **Vorschlag** (`idea`, `organization = null`); 422 `proposal_quota_exceeded`, wenn die Person schon 5 offene Vorschläge hat (`state = idea AND organization_id IS NULL AND created_by = sub`; Zählen und Anlegen unter `pg_advisory_xact_lock(hashtext(sub))`) |
| `GET /events/{id}` | `library.read` | | `EventOut` mit `ETag`; 404 ohne Leserecht |
| `PATCH /events/{id}` | `event.edit` | `EventPatch` (3.1) plus `If-Match` | 200 `EventOut` mit neuer `ETag`; 409 `conflict` (Version), 409 `field_locked`, 403, 404, 422 (Guards der Live-Änderung, `validation_error`), 428 |

**Sichtbarkeit (PLAN 5.4, ändert `visible_events_query` und `load_visible`):** zusätzlich zur Org-Menge liest eine Person Dossiers mit `organization_id IS NULL AND created_by = sub` (ihre eigenen Vorschläge), und nur diese. Das aktiviert den `xfail`-Test; der Marker fällt weg. Mit `assign_organization` endet die Lesbarkeit für die vorschlagende Person, sofern sie keine Rolle in der Org hat (D7).

### 5.3 Übergänge und Guards

| Methode Pfad | Gate | Request | Antwort / Fehler |
|---|---|---|---|
| `POST /events/{id}/transitions/{T}` | `library.read` | `TransitionIn`, optional `If-Match` | 200 `EventOut`; 403 `forbidden` oder `four_eyes`; 404; 409 `invalid_transition` / `conflict`; 422 `reason_required`, `publish_at_in_past`, `publish_after_end`, oder der Code des ersten Blockers mit `reasons[]` |
| `GET /events/{id}/guards/{T}` | `library.read` | | 200 `{ transition, allowed, reasons[] }`; berechnet, nie gespeichert; für `forbidden`/`invalid_transition` wie M1 ein Blocker-Eintrag |

`{T}` ist jede der 14 Ids. `GET .../guards/T08` für einen Menschen liefert `allowed=false` mit `forbidden`.

### 5.4 Aktionen

`POST /events/{id}/actions/{name}`, Antwort 200 `EventOut` (mit `ETag`), optional `If-Match`. Pflichtgrund und Wirkung: Abschnitt 2.4.

| Pfad | Gate | Body |
|---|---|---|
| `.../actions/cancel` | `event.cancel` | `{ reason, publicReasonCode = "none", publicReasonText? }` |
| `.../actions/postpone` | `event.cancel` | `{ reason, publicReasonCode, publicReasonText?, newStartsAt?, newEndsAt? }` (`newEndsAt` nur mit `newStartsAt`; ohne `newEndsAt` bleibt die Dauer) |
| `.../actions/reinstate` | `event.approve` | `{ reason }` |
| `.../actions/image-exception` | `event.image_exception` | `{ reason }` (>= 10 Zeichen); der M1-Pfad `POST /events/{id}/image-exception` bleibt als Alias bis M4 (`deprecated=True`, derselbe Handler) |
| `.../actions/assign-organization` | `event.assign_org` | `{ organizationId }` |
| `.../actions/revert-revision` | `event.edit_critical_live` | `{ rev, note? }` |
| `.../actions/acknowledge-changes` | `event.edit_critical_live` | `{}` |
| `.../actions/confirm-flyer` | `event.edit` | `{}` |

Fehler: 403 (Recht in der Org fehlt), 404 (nicht lesbar), 409 `invalid_transition` (Zustand oder `public_status` passt nicht), 409 `organization_already_set`, 409 `revert_poster_replaced`, 409 `conflict`, 422 `reason_required` / `start_in_past` / `validation_error` / Live-Guards.

### 5.5 Entwurf, Revisionen, Aufgaben

| Methode Pfad | Gate | Request | Antwort |
|---|---|---|---|
| `PUT /events/{id}/draft` | `event.edit` | `{ fields }`, `If-Match` | 200 `DraftOut`; 409 `conflict` (mit `current`), 409 `field_locked`; 413 bei > 64 KiB |
| `GET /events/{id}/draft` | `event.edit` | | 200 `DraftOut` oder 204 |
| `DELETE /events/{id}/draft` | `event.edit` | | 204 |
| `GET /events/{id}/revisions` | `library.read` | Query `fieldClass?`, `limit` (1..200, 50), `offset` | `Page<RevisionOut>`, absteigend nach `rev` |
| `GET /events/{id}/revisions/{rev}` | `library.read` | | `RevisionDetail`; 404 |
| `GET /tasks` | `library.read` | | `TasksOut` |

`TasksOut`: jede Liste höchstens 50 Einträge, dazu `counts` mit der vollen Zahl.

```
TasksOut { awaitingReview: (EventCard + { fourEyesBlocked })[],   # in_review, Aufrufer darf T04 und hält event.approve in der Org
           returned: (EventCard + { note, returnedAt, returnedBy })[],   # planning, letztes Status-Event ist T03, Aufrufer hält event.edit in der Org
           due: [],                                   # Checklistenpunkte: M4, bis dahin immer leer
           mine: EventCard[],                         # offene Dossiers (idea..approved): Org-Rollen alle der eigenen Orgs, sonst created_by/submitted_by
           followupOpen: EventCard[],                 # followup, Aufrufer hält event.submit in der Org
           changedAfterPublish: (EventCard + { baselineRev, changes: RevisionOut[] })[],   # 3.6, nur mit event.edit_critical_live
           counts: { awaitingReview, returned, due, mine, followupOpen, changedAfterPublish } }
```

`fourEyesBlocked = true`, wenn der Aufrufer `submitted_by` ist und `Actor.four_eyes` gilt (die UI zeigt "Eine andere Person muss freigeben."). `returned.note` ist die Pflichtnotiz von T03, also die Rückfrage (M4 ergänzt Kommentare mit Anker).

### 5.6 Öffentlicher Feed und View (Migration 0004)

`public_event_v` wird um `public_reason_code`, `public_reason_text` erweitert (Spalten am Ende, `CREATE OR REPLACE VIEW`) und liefert `venue_text` als Name des Ortes, wenn `venue_id` gesetzt ist und der Ort nicht `is_private` ist; bei `is_private` ist es `NULL`; ohne `venue_id` unverändert `venue_text`. `PublicEventOut` bekommt `statusReason: { code, text|null } | null` (`null` bei `scheduled`); `tests/schema/feed-v2.json` wird additiv angepasst. Ein Dossier mit `public_status = cancelled | postponed` bleibt im Feed (Zustand `live`, `followup`, `archived`); `events_public` sieht weiter nur die View. Interne Inhalte (`note`, Grund, `image_exception`) erscheinen nie (Kanarienvogel-Test aus M1 bleibt grün).

### 5.7 Problem+JSON: neue und geänderte Codes

| Status | `code` | Wann |
|---|---|---|
| 403 | `four_eyes` | freigebende Person hat eingereicht (2.5); mit `reasons[]` |
| 409 | `conflict` | Version veraltet; Erweiterungen `current`, `currentRev` |
| 409 | `field_locked` | Feld oder Klasse im Zustand gesperrt; `errors[{field,msg}]` |
| 409 | `revert_poster_replaced`, `organization_already_set`, `quarantined` | s. 5.4; `quarantined`: `GET .../poster/file` für ein Poster mit `scan_status = infected` (U-GUARD-07) |
| 422 | `reason_required` | Pflichtnotiz bzw. Pflichtgrund leer |
| 422 | `proposal_quota_exceeded` | 5 offene Vorschläge |
| 422 | `publish_at_in_past`, `publish_after_end` | T04 |
| 422 | `unknown_venue` | `venueId` unbekannt oder inaktiv |
| 422 | alle Codes aus 2.3 | Guard als Blocker |
| 428 | `precondition_required` | `PATCH`/`PUT draft` ohne `If-Match` und ohne `rev` |

### 5.8 Routen-Inventur (`ROUTE_PERMS`, M2 Abschnitt 7)

Neu oder geändert: `GET/POST /api/events` und `GET /api/events/{event_id}`: `library.read`; `PATCH /api/events/{event_id}`: `event.edit`; `POST .../transitions/{transition}` und `GET .../guards/{transition}`: `library.read`; Aktionen: Recht je Pfad (5.4); `PUT/GET/DELETE .../draft`: `event.edit`; `GET .../revisions`, `.../revisions/{rev}`, `GET /api/tasks`: `library.read`. Die Inventur schlägt an, wenn eine dieser Routen fehlt oder ein Gate ohne Recht bleibt. Neue Rolle/Recht: `event.restore` im Katalog (nur `editor`; `admin` über den Bypass), `test_permission_catalogue` wird angepasst.

## 6. Worker: `advance_states`

Neue Dateien: `app/modules/pipeline/advance.py` (reine Entscheidung, 100 % Branch) und `worker/advance.py` (Lauf), Eintrag in `worker/main.py`.

| Aufgabe | Ausdruck | Wirkung |
|---|---|---|
| `advance_states` | `cron(advance_states, minute={0, 15, 30, 45}, timeout=300)`, arq-Cron `unique` | für jedes fällige Dossier genau ein Übergang je Lauf |
| `purge_drafts` | `cron(purge_drafts, hour=3, minute=30)` | löscht `editor_draft`-Zeilen mit `updated_at < now - 14 Tage` |

Reine Funktion `due_transition(row: AdvanceRow, now) -> TransitionId | None` mit `AdvanceRow(state, publish_at, ends_at, origin_kind, entered_followup_at)`:

| Zustand | Bedingung | Id |
|---|---|---|
| `approved` | `publish_at IS NOT NULL AND publish_at <= now` | T05 |
| `live` | `ends_at + 12 h <= now` und `origin_kind IN (internal, mcp)` | T08 |
| `live` | `ends_at + 12 h <= now` und `origin_kind IN (imported, legacy)` | T08b |
| `followup` | `entered_followup_at + 30 d <= now` | T09b |
| sonst | | `None` |

`approved` ohne `publish_at` wartet auf den Menschen (T05), damit der Worker kein manuelles "Veröffentlichen" überholt (Abweichung 12.17, D5). `entered_followup_at` ist `max(at)` der `event_status_event`-Zeilen mit `to_state = followup`.

Der Lauf: (1) SQL-Vorauswahl der Kandidaten je Zustand, `ORDER BY` Fälligkeit, `LIMIT 200` je Klasse; (2) je Kandidat eine **eigene Sitzung und Transaktion**: `PipelineService.stage_system_fire(event_id, transition_id, now)`, Commit, dann `run_actions` mit dem arq-Pool aus `ctx["redis"]`; (3) ein Fehler eines Dossiers bricht den Lauf nicht ab (`logger.exception`, Zähler `failed`); (4) Rückgabe `published=… followup=… archived=… blocked=… skipped=… failed=…` für das arq-Log.

**Keine Umgehung der Bildpflicht:** `stage_system_fire` ruft dieselbe `decide`-Funktion wie die REST-Route, mit `SYSTEM_ACTOR`. Es gibt keinen `system_context`, keinen Sonderpfad und keinen zweiten Schreibweg auf `state`. Ist das Poster inzwischen nicht mehr gültig (Scan geändert, ausgeblendet), blockt `image_required` den Worker-T05: `blocked += 1`, das Dossier bleibt `approved`, Log `advance_blocked event=<id> code=<code>`. Der Trigger `enforce_publish_image` bleibt das zweite Netz. Weitere Sicherungen für Sys-T05: `humanApproval` (`approved_by` ist eine Person, nie `system:*`, damit weder Worker noch Import noch MCP je ohne Mensch `live` erreichen) und `dateInFuture`. Ein Konflikt (ein Mensch war schneller, `ConflictError`) zählt als `skipped`. Status-Event und Revision tragen `actor_id = "system:advance_states"`, `actor_type = system`; das Audit schreibt `EVENT_TRANSITION` mit demselben Akteur.

Zeitzone: Alle Fälligkeiten sind absolute `timestamptz`-Vergleiche; der Cron läuft im Viertelstundentakt, ist also von UTC gegen Berliner Uhrzeit unabhängig (PLAN 18, offener Minor-Befund betrifft nur Tages-Crons).

## 7. Datenmodell-Delta (Migration `0004_pipeline_full`)

Genau ein Head `0004_pipeline_full` (<= 32 Zeichen), auf `0003_roles_taxonomy`. Frische DB und M3-Upgrade ergeben dieselben Zeilen (`test_migrations`). `models.py` wird mitgeführt.

| Tabelle | Änderung |
|---|---|
| `event` | `ticket_url text`, `website_url text` (CHECK `~ '^https://[^/@\s]+\.[^/@\s]+'`, Länge <= 500, keine Steuerzeichen), `cost_text text` (<= 200, ohne Steuerzeichen), `venue_id uuid` (FK `venue.id` `RESTRICT`, Index), `publish_at timestamptz`, `public_reason_code text NOT NULL DEFAULT 'none'` (CHECK `none,room,speaker,illness,registration,weather,other`), `public_reason_text text` (<= 140, ohne Steuerzeichen), CHECK `public_status <> 'scheduled' OR (public_reason_code = 'none' AND public_reason_text IS NULL)`, `end_estimated boolean NOT NULL DEFAULT false`, `flyer_checked_at timestamptz`, `text_reviewed_rev integer NOT NULL DEFAULT 0`, `published_rev integer` |
| `event_status_event` | `four_eyes boolean NOT NULL DEFAULT false`, `submitted_by text`, CHECK `ck_event_status_event_four_eyes` (2.5); Append-only-Trigger bleibt |
| `editor_draft` | neu (4.3) |
| `attachment_poster_ok(attachment)` | `CREATE OR REPLACE`: zusätzlich `AND (NOT a.persons_depicted OR btrim(coalesce(a.consent_note, '')) <> '')` (Netz für `rights_incomplete`; die Spalten `persons_depicted`, `consent_note` existieren schon) |
| `public_event_v` | `CREATE OR REPLACE VIEW`: Spalten `public_reason_code`, `public_reason_text` am Ende; `venue_text` aus dem Ort (5.6); `LEFT JOIN venue v ON v.id = e.venue_id` |
| Rechte | `GRANT SELECT, INSERT, UPDATE, DELETE ON editor_draft TO events_app` (in der Migration bedingt wie `_GRANTS` in `0002`, und in `deploy/db/roles.sql` Stufe 2 mit `DELETE`); `events_public` sieht weiter nur die View |

Bestandsdaten bleiben gültig: alle neuen Spalten sind nullable oder haben einen Standard. Die Zuordnung `PosterSnapshot`/`Snapshot` wächst um die Felder dieses Abschnitts (`venue_id`, `ticket_url`, `website_url`, `cost_text`, `publish_at`, `public_status`, `end_estimated`, `flyer_checked_at`, `approved_by`, `origin_kind`, `duplicate_score`, `open_hero_comments`, `open_required_checklist`, `facts_error`, `open_proposals`, `entered_followup_at`, `consent_ok`, `reused_in_other_year`) mit neutralen Standardwerten, damit bestehende Tests mit `snap(...)` weiterlaufen.

`seed_dev` bekommt `stage: in_review | approved | live | followup | archived` (über den Service, Bild über `imageException`) und einen Vorschlag der Person `member`; zweimal laufen legt nichts Neues an (`test_seed_dev`).

## 8. Frontend

Besitz: `frontend/**`. Angular standalone, OnPush, Signals, getrennte `.html`/`.scss`, i18n de (gegendert mit Doppelpunkt oder neutral), Du-Form, Komponenten aus `@stupa-makers/ui-kit` und `@shared/ui`, nie natives `<select>`, Status nur als farbiger Text (PLAN 15.0). Kopien aus Upstream mit Herkunftsvermerk und `PROVENANCE.json`-Eintrag (Modus `U`, nach Lesen der Quelle).

### 8.1 Routen und Navigation

- Neuer Eintrag `Pipeline` in `NAV_ITEMS` (`key: 'pipeline'`, `/pipeline`, `permissions: []`, Icon `kanban`; der Eintrag `dossiers` wechselt auf ein anderes Icon aus dem Kit, die Liste I04 erreicht man auch über den Knopf "Liste" im Board).
- `feature-routes.ts`: `pipeline` (`wide: true`, `fab: true`, `authGuard`), `aufgaben`, `dossiers` (mit Kinderroute `:id` im Listen-Detail-Layout, I04), `dossiers/neu`, `dossiers/:id` (`canDeactivate: [pendingChangesGuard]`). `dossiers/neu` bleibt vor `dossiers/:id`.
- `core/auth/pending-changes.guard.ts` (`CanDeactivateFn`): hat die Seite ungespeicherte oder nicht gesendete Änderungen, öffnet er den Dialog "Speichern · Verwerfen · Bleiben". Dazu `beforeunload`, solange `dirty`.

### 8.2 Neue Bausteine in `shared/ui` (Kopien, PROVENANCE)

`pipeline-board/` (Fork `U frontend/src/app/pages/todos/board-view/*`: `CdkDropListGroup`/`CdkDrag`, Tastatur-Drag, Phone-Pager), `avatar/`, `row-menu/`, `search-pill/`, `filter-select/` (je mit `U frontend/src/app/shared/ui/<name>/*`), `shared/long-press.directive.ts`, `shared/scroll-fade.directive.ts`. Alles wird im Barrel `shared/ui/index.ts` geführt; Code im Anfangsbündel importiert weiter per Pfad.

### 8.3 I03 Pipeline-Board (`/pipeline`)

- Daten: `GET /events?view=board` plus Filter; `app-filter-bar` (Kit) mit `app-filter-select` Organisation, Kategorie, Zeitraum (`from`/`to`), Schalter "nur meine", `app-search-pill` (live, 250 ms Verzögerung) und Ansicht "Aktiv | Archiv | Verworfen". Die Filter stehen als Query-Parameter in der URL und überstehen Reload und Zurück. Format-Filter: M5.
- Spalten (`app-pipeline-board`): Idee · Planung · Freigabe · Veröffentlicht · Nachbereitung mit Zähler (`total`), Archiv/Verworfen als eigene Ansicht. "Veröffentlicht" enthält `approved` und `live`; die Karte nennt den Unterschied als Text ("geplant ab 01.11." bei `approved` mit `publishAt`, "Freigegeben" ohne, "Abgesagt" in Fehlerfarbe, "Verschoben" in Warnfarbe).
- Karte: Titel, Datum (`Do., 5. Nov.`), Organisation (Kurzname), Ort (`venueLabel`), erste Blocker (`blockers`, z. B. "Poster fehlt"), `blockerCount`, Avatar der erstellenden Person (D8), Zahl offener Rückfragen (erst ab M4 > 0). Die Karte ist ein Knopf (öffnet I07).
- **Drag (Maus/Touch-Desktop):** `cdkDragData = card.id`; eine Spalte nimmt die Karte nur an, wenn `card.moves[spalte]` existiert (`cdkDropListEnterPredicate`). Andere Spalten zeigen beim Darüberfahren "Nicht möglich: …" (`board.notPossible`), die Karte springt beim Loslassen zurück. Ein erlaubter Drop öffnet **I13** mit dem Übergang (T01 ausgenommen: T01 feuert direkt, Fehler als Toast). Antwortet der Server mit 422, springt die Karte zurück und der Toast nennt die Gründe ("Verschieben nicht möglich: Poster fehlt, Ort fehlt."); bei 409 lädt das Board neu ("Diese Karte wurde inzwischen geändert. Board neu geladen.").
- **Tastatur-Drag (Muster Upstream):** Leertaste hebt die fokussierte Karte (`aria-pressed`), Pfeil links/rechts wechselt die Spalte (auch in nicht erlaubte; die Live-Region sagt "Spalte Planung, Verschieben möglich" bzw. "nicht möglich"), Leertaste/Enter legen ab (erlaubt: I13 bzw. T01 direkt; nicht erlaubt: Karte bleibt gehoben und die Live-Region sagt "nicht möglich"), Escape legt zurück. Auf/ab ist ohne Wirkung (die Reihenfolge ist das Datum). Live-Region `aria-live="assertive"`: "„Movienight“ aufgenommen, Spalte Idee." · "„Movienight“ nach Planung verschoben." Der Tastatur-Drag endet bei Fokus- oder Zeigerwechsel (wie Upstream `leaveDrag`).
- **Handy** (Kit-Breakpoint `narrow`): `app-tabs` mit Zählern über einem horizontalen Scroll-Snap-Pager, eine Spalte je Seite, Wischen wechselt die Spalte, ein Tipp auf den Tab scrollt hin; **kein Drag**. Langes Drücken (`LongPressDirective`, 400 ms, ein Finger-Drift bricht ab) öffnet ein Bottom-Sheet "Verschieben" (`app-side-sheet`) mit den erlaubten Übergängen der Karte (`allowedTransitions`, Beschriftungen aus `TRANSITION_LABEL`), jeder Eintrag öffnet I13. `prefers-reduced-motion` schaltet das sanfte Scrollen aus.
- Aktualisierung: bei Fokus des Fensters (`visibilitychange`) und alle 60 s, pausiert, solange eine Karte gehalten wird oder ein Dialog offen ist.
- Leer: je Spalte "Keine Events in dieser Phase."; gesamt "Noch keine Events. Leg das erste an." mit Knopf "Neues Event" (I05). Laden: `app-skeleton`.

### 8.4 I04 Dossier-Liste (`/dossiers`, `/dossiers/:id`)

`app-list-detail` (breit nebeneinander ab `LIST_DETAIL_SPLIT_MIN`, sonst eine Ansicht mit "Zur Liste"); Zeile `app-list-item`: Datum, Titel, Organisation, Zustand als Text, Blocker-Zahl; Sortierung nach Datum; **dieselben Filter und Filterchips wie I03** (gemeinsame Komponente `features/pipeline/filters`); Fokusrückgabe und Scrollposition bleiben beim Zurück. Der Umschalter Liste/Kalender entfällt in M3 (`app-calendar-grid` ist M5, Abweichung 12.9). Leer: "Keine Dossiers für diese Filter." mit "Filter zurücksetzen".

### 8.5 I05 Neues Event oder Vorschlag

`app-dialog` (Handy Bottom-Sheet). Felder: Titel, Organisation (`app-select` mit `GET /organizations?creatable=true`; hat die Person keine, ist das Feld fest "Vorschlag, ohne Organisation" und gesperrt), Beginn (Datum + Uhrzeit, Europe/Berlin), optional Ende (leer: "Ende wird auf Beginn + 2 Stunden gesetzt", Hinweis), Kategorie (`app-select` über den Baum). Hinweis bei Vorschlag: "Die Redaktion ordnet deinen Vorschlag einer Organisation zu." Fehlertexte: "Titel fehlt." · "Beginn fehlt." · `proposal_quota_exceeded`: "Du hast schon 5 offene Vorschläge. Warte, bis die Redaktion sie bearbeitet hat." · 404 bei fremder Org: "Für diese Organisation darfst du keine Events anlegen." "Aus Vorlage" (I06) und "Instagram-Post" erscheinen erst mit M5/M6.

### 8.6 I07 Dossier: Kopf und Übersicht (`/dossiers/:id`)

Aufgeteilt in kleine Komponenten (`features/dossiers/`): `head/` (Titel, Zustand, `public_status` mit öffentlichem Grund als Text, Organisation, Datum; Übergangsmenü mit `allowedTransitions`; primärer Knopf je Zustand `idea: T01, planning: T02, in_review: T04, approved: T05, followup: T09` (nur wenn erlaubt); Menü "Mehr" mit `allowedActions` und den übrigen Übergängen: Absagen/Verschieben (I14), Absage zurücknehmen, Ausnahme ohne Bild (I15, nur Redaktion), Organisation zuweisen (Dialog, nur Redaktion bei Vorschlag), Änderungen anfragen (T03), Freigabe zurücknehmen (T06), Offline nehmen (T07), Verwerfen (T11), Wiederherstellen (T12), Wieder öffnen (T10)), `overview/` ("Fehlt noch" `app-guard-list` des nächsten Übergangs, Kerndaten in `app-field-group` getrennt nach "Kritisch" und "Text"), `form/` (Eingabefelder mit Sperre aus `editableFields`/`lockReason`), `autosave/` (Controller und Anzeige), `conflict/` (Dreiwege-Dialog mit `app-config-diff`), `history/` (minimaler Tab "Verlauf": Revisionen mit `changedFields`-Chips und "Auf diesen Stand zurücksetzen" für Ap/Ed; Kommentare, Diff und Anker sind M4/I12).

- **Sperren:** Felder ohne Eintrag in `editableFields` sind gesperrt und tragen den Hinweis nach `lockReason`: `in_review`/`approved`: "In der Freigabe gesperrt. Kommentiere, wenn sich etwas ändern soll." (Kommentieren selbst: M4); `live_critical`: "Änderung von Zeit, Ort, Titel oder Poster geht über die Redaktion." (der Knopf "Änderung anfragen" folgt mit M4); `closed`: "Dieses Dossier ist abgeschlossen."
- **Autosave-Anzeige** am Formular: "Gespeichert 14:02" · "Speichert …" · "Nicht gespeichert" (geändert, noch nicht gesendet) · "Nicht gespeichert, offline".
- **Autosave-Controller** (`DraftAutosave`, Signals): sammelt Änderungen, sendet 15 s nach der ersten ungesendeten Änderung `PUT /draft` mit `If-Match = rev`, danach alle 15 s, solange Änderungen anliegen; "Speichern" ruft `PATCH` mit `If-Match` und löscht den Entwurf; 30 Minuten ohne Eingabe wenden den Entwurf per `PATCH` an (nicht in `in_review`, `approved`, `live`: dort bleibt er Entwurf bis zum ausdrücklichen Speichern). Offline (`navigator.onLine`, Netzfehler): Fassung in `localStorage` (`try/catch`, Schlüssel `draft:<eventId>:<sub>`), Toast "Keine Verbindung. Deine Änderungen sind lokal gespeichert und werden gesendet, sobald du wieder online bist.", Senden bei `online`. **Beim Öffnen** `GET /draft`: vorhanden und `baseRev = rev` stellt die Felder wieder her (Hinweis "Entwurf von 14:02 wiederhergestellt. [Verwerfen]"), `baseRev < rev` öffnet den Konfliktdialog. Der Service-Worker-Update lädt nie von selbst neu (M1).
- **409** bei `PUT`/`PATCH`/Übergang: Toast "Jemand anderes hat das Dossier geändert. [Unterschiede ansehen]"; der Dialog zeigt Basis, "Deins" und "Neu" je Feld (`app-config-diff`) und lässt je Feld wählen; "Übernehmen" sendet `PATCH` mit `If-Match = current.rev`.
- **Nachträglich geändert (Prüfende):** Banner über der Übersicht "Seit der Veröffentlichung geändert: Kurztext (Anna, 14:02)" mit "Zurücksetzen" (bestätigt, `revert-revision` auf `baselineRev`) und "Gesehen" (`acknowledge-changes`).
- Fehler: "Freigabe nicht möglich: Poster fehlt, Ort fehlt." · "Diese Felder sind in der Freigabe gesperrt." · "Ende liegt vor dem Beginn." · "Ticket-Link muss mit https:// beginnen."
- `app-poster-upload` bleibt (Zustände nach 2.1); die Felder `Personen erkennbar` und `Einwilligung` kommen als zwei zusätzliche Formularfelder (`personsDepicted`, `consentNote`) an `POST .../poster` (additiv; M4 baut I08 aus). Das Orts-Feld ist ein `app-select` über `GET /venues` mit Freitext-Alternative.

### 8.7 I13 Übergang bestätigen

`app-dialog`: Titel aus `TRANSITION_LABEL` (alle 14 Ids, Sys-only nur als Verlaufstext); `app-guard-list` aus `GET /guards/{T}` (Blocker oben, Warnungen darunter, Warnungen mit Bestätigungs-Häkchen "Ich habe die Hinweise gelesen"); **Pflichtnotiz** bei T03, T06, T07, T10, T11 (Beschriftung je Übergang: "Was soll sich ändern?", "Warum nimmst du die Freigabe zurück?", "Warum nimmst du das Event offline?", "Warum öffnest du es wieder?", "Warum verwirfst du es?"); bei T04 das Feld "Veröffentlichen am" und der Schalter "Sofort veröffentlichen" (an, solange das Feld leer ist; mit Wert aus, dann veröffentlicht der Worker; D5); Vier-Augen-Hinweis bei Vorliegen von `four_eyes` oder `fourEyesBlocked`: "Du hast dieses Event eingereicht. Eine andere Person muss freigeben." Der Knopf ist deaktiviert und nennt den Grund als sichtbaren Text (`aria-describedby`). Fehler: "Nicht möglich: Poster fehlt." · "Bitte gib einen Grund an." · "Ein anderer Übergang war schneller. Zustand ist jetzt: Freigegeben." (409, lädt neu). Nach T04 mit "Sofort" folgt T05 als zweiter Aufruf; scheitert er, bleibt das Dossier `approved` und der Dialog sagt es.

### 8.8 I14 Absagen oder Verschieben, I15 Ausnahme ohne Bild

I14: `app-segmented` Absagen/Verschieben; Grund (Pflicht, intern, <= 500); "Öffentlicher Grund" als `app-select` mit den sieben Codes (Raum nicht verfügbar, Referent:in verhindert, Krankheit, zu wenig Anmeldungen, Wetter, Sonstiges, ohne Angabe); öffentlicher Kurztext (<= 140) nur für Personen mit `event.approve`; bei Verschieben "Neuer Termin" (Datum/Zeit, nur mit `event.edit_critical_live`) oder fest "neuer Termin folgt"; Hinweis "Abonnent:innen sehen die Absage in ihrem Kalender, je nach App mit bis zu einem Tag Verzögerung."; Knopf `danger`. Fehler: "Grund fehlt." · "Neues Datum muss in der Zukunft liegen." I15 wie M1 (Grund >= 10 Zeichen, Beispiel, Hinweis "Gilt nur für dieses Event, nicht für Kopien und Serientermine."), neuer Pfad `/actions/image-exception`, nur für Personen mit `event.image_exception`.

### 8.9 I02 Meine Aufgaben

`app-page-header`; Abschnitte als `app-card` mit Zähler (`app-badge`) nach `GET /tasks`: "Wartet auf deine Freigabe" (mit Ampel "in 3 Tagen", `fourEyesBlocked` als Hinweis), "Rückfragen an dich" (Notiz, Person, Datum), "Fällig" (erscheint erst, wenn M4 Einträge liefert), "Meine Dossiers" (nach Zustand gruppiert), "Nachbereitung offen", "Nachträglich geändert" (nur mit Einträgen; "Zurücksetzen" und "Gesehen"). Fab "Neues Event" auf dem Handy. Leer: "Gerade nichts zu tun. Leg ein neues Event an oder schau ins Archiv." mit Knopf. Pro Abschnitt eine Überschrift (`h2`) für Screenreader-Navigation.

### 8.10 i18n, API-Client, Typen

Neue Schlüssel in `core/i18n/translations.pipeline.de.ts` (Board, Aufgaben, I13 bis I15, Autosave, Konflikt, Verlauf) und `translations.events.de.ts` (`guards.<code>` für alle Codes aus 2.3, `fix.<fixAction>` für alle 15 Werte, `event.state.*`, `transition.*` für 14 Ids, `lock.*`, `publicReason.*`); `TranslationKey` bleibt ein typsicherer Schlüssel, der Gender-Lint (E32) läuft in `npm run lint`. `EventsApi` wächst um `board`, `listCards`, `tasks`, `action`, `draft*`, `revisions`, `patch` mit `If-Match` (liest `ETag` über `observe: 'response'`); Typen von Hand (`board.models.ts`, `task.models.ts`, `action.models.ts`), identisch benannt wie Abschnitt 5.1; `TransitionId` mit 14 Werten. Ein Konstanten-Test prüft `BOARD_MOVES` und `TRANSITION_LABEL` gegen die 14 Ids.

### 8.11 Dateien

`features/pipeline/{pipeline.routes.ts, pipeline-page.component.*, filters/, board-card/, move-sheet/}`, `features/dossiers/{head,overview,form,autosave,conflict,history,transition,cancel,exception,new-event,list}/`, `features/tasks/{tasks.component.*, task-section/}`, `shared/ui/{pipeline-board,avatar,row-menu,search-pill,filter-select}/`, `core/auth/pending-changes.guard.ts`, `core/i18n/translations.pipeline.de.ts`, `e2e/m3.spec.ts`, `e2e/support/axe.ts`. Jede Datei bleibt unter etwa 250 Zeilen, Kopf-Docstring je Datei, keine Trennkommentare.

## 9. Tests

Namen sind fest, damit das Review sie findet. Backend-Tests liegen unter `backend/tests/**`, Frontend-Specs neben der Komponente, E2E unter `frontend/e2e/`.

### 9.1 Backend, Unit (`pytest -m 'not integration and not e2e and not live'`)

| Test | Inhalt |
|---|---|
| `tests/unit/pipeline/test_transitions_matrix.py` (neu aufgesetzt) | **Vollmatrix** Zustand (8) × Übergang (14) × Akteur (`viewer`, `member`, `submitter` eigene, `submitter` fremde, `organizer`, `approver`, `editor`, `admin`, `stupa`, `system`) × Bild (gültig, fehlt, gültige Ausnahme) × Vier-Augen (Akteur ist `submitted_by`, andere Person, `submitted_by` leer) × Zeit (laufend, vorbei). Erwartung aus der **eigenständigen Orakel-Tabelle** `tests/unit/pipeline/oracle.py` (PLAN 4.3 als Literal, importiert nicht `TRANSITIONS`); ein Test je Übergang prüft das Produkt in einer Schleife und meldet alle Abweichungen gesammelt. Zusätzlich: `TRANSITIONS` und Orakel haben dieselben 14 Ids, dieselben Quell-/Zielzustände und dieselbe Rolle je Übergang |
| `test_guards.py` (erweitert) und `test_u_guard.py` (neu) | je Guard-Code aus 2.3 ein positiver und ein negativer Fall (alle 26 Zeilen), feste Reihenfolge der `reasons[]`, Warnungen blocken nie; **U-GUARD-01 bis 13** unter diesen Namen (`test_u_guard_01_editor_with_poster_allowed` ... `test_u_guard_13_two_concurrent_approvals_one_wins`): 01 Redaktion mit Poster erlaubt · 02 ohne Poster 422 `image_required` · 03 Ausnahme mit Grund erlaubt · 04 Ausnahme ohne Grund (< 10 Zeichen) 422 · 05 fremde Org 404 (Integration) · 06 System/Import/MCP nie `live` ohne Mensch (`humanApproval`, Sys feuert kein T04) · 07 Quarantäne: Poster `infected`/`pending` blockiert T04/T05, `GET poster/file` 409 `quarantined` (Integration) · 08 Entfernen/Ersetzen des Posters in `live` 409 (Upload `field_locked`, Direkt-SQL 23514; Integration) · 09 laufendes Event erlaubt · 10 vergangenes 422 `start_in_past` · 11 Dublette 422 `duplicate_unresolved` (Guard gegen `duplicate_score = 0,9`) · 12 gleiche Entscheidung über REST, Worker, Fabrik (Property, s. u.) · 13 zwei gleichzeitige Freigaben, genau eine gewinnt (Integration, `asyncio.gather`) |
| `test_publish_property.py` (erweitert) | Hypothesis-Zustandsmaschine über **alle** Übergänge, Aktionen (`cancel`, `postpone`, `reinstate`, `revert`, `image_exception`), Poster-Wechsel und Worker-Läufe: nie ein Zustand `approved`/`live` ohne gültiges Poster oder gültige Ausnahme **zum Zeitpunkt des Eintritts**; nie `live` ohne menschliche Freigabe; Sys feuert nur T05, T08, T08b, T09b; `public_status <> scheduled` nur ab `live`; `decide` liefert für denselben Snapshot dasselbe Ergebnis über `stage_fire` (REST), `stage_system_fire` (Worker) und die Direkt-Schreibweise des Fabrik-Helfers (der Trigger lehnt sie ab, wenn `decide` es tut) |
| `test_fieldclass.py` | `plan_patch`: Entscheidungstabelle 3.2 (Zustand × Akteur × Klasse) generiert; alles-oder-nichts bei gemischten Feldern; `public_seq`-Regel 3.5; Klassifikation `critical`/`text`; `link_hosts` (http/https, `www.`, Port, Großschreibung, IDN, `mailto:` ignoriert, Mehrfachtreffer); neuer Host macht Text kritisch, bekannter Host nicht; URL-Validierung (`http://`, Benutzerteil, zu lang) |
| `test_actor.py` | `actor_of`: `kind` und `four_eyes` für Redaktion (mit/ohne `EDITOR_FOUR_EYES`), `admin`, Org-Approver, `organizer`; `SYSTEM_ACTOR` |
| `test_advance.py` | `due_transition` Tabelle aus Abschnitt 6 mit Grenzwerten (11:59, 12:00, 12:01 nach Ende; 29 und 30 Tage; `publish_at` genau jetzt, `NULL`) und allen `origin_kind` |
| `test_board_moves.py`, `test_catalogue.py` | `BOARD_MOVES` stimmt mit `TRANSITIONS` überein; `event.restore` nur bei `editor`; Katalogbericht |
| `test_route_authz_inventory.py` (erweitert) | `ROUTE_PERMS` mit allen neuen Routen (5.8); Meta-Tests bleiben |
| `test_camel_case_contract.py`, `test_schemas.py` | alle neuen Modelle camelCase, `extra=forbid`; `TransitionIn.publishAt` nur aware; `EventCreate.endsAt` optional; Aktions-Bodies |
| `tests/unit/worker/test_advance_states.py`, `test_purge_drafts.py` | Lauf mit Fake-Sitzungen, Fehlerisolierung je Dossier, Zähler im Rückgabestring |

### 9.2 Backend, Integration (`pytest -m integration`, Docker)

| Test | Inhalt |
|---|---|
| `tests/integration/events/test_rbac_matrix.py` (erweitert) | Zeilen wie M2 plus `approver2-stupa` (zweite Person der trusted Org `stupa`, im Harness und im Realm ergänzt); Operationen: Lesen, Liste, Anlegen mit/ohne Org, Ändern, **jeder der 14 Übergänge**, jede Aktion, Entwurf, Revisionen, Tasks. Erwartung exakt (kein `{403, 404}`). Geändert gegenüber M2 (Abschnitt 12.10): `member`, `nobody`, `viewer` legen ohne Org einen Vorschlag an (201), Übergänge laufen mit Session-Gate: fremdes Dossier 404, sichtbares ohne Recht 403 |
| `tests/integration/events/test_visibility.py` | `xfail` entfernt: `member` liest den eigenen Vorschlag (200), nicht den anderer (404); nach `assign-organization` 404 für die vorschlagende Person |
| `tests/integration/pipeline/test_full_flow.py` | T00 bis T05, danach T08 mit fester Uhr über den Worker, T09; Schleife T02, T03 (mit Notiz), T02, T04; T06; T07 (Feed leer, `public_seq`); T11 und T12; T10 durch die Redaktion; `reason_required` je Pflichtnotiz-Übergang; Status-Events und Revisionen lückenlos, `actor_type = system` beim Worker |
| `test_four_eyes.py` | **trusted Approver gibt eigene Einreichung nicht frei:** `approver-stupa` reicht ein (T02) und feuert T04 → **403 `four_eyes`** mit `reasons[]`; `approver2-stupa` gibt frei (200); `editor` gibt eigene frei (200, Audit `selfApproved`); mit `EDITOR_FOUR_EYES=true` 403 für den Editor; `admin` ist gebunden; Direkt-INSERT einer `event_status_event`-Zeile `T04`, `four_eyes = true`, `actor_id = submitted_by` scheitert mit SQLSTATE `23514` (`ck_event_status_event_four_eyes`); `submitted_by IS NULL` blockt |
| `test_field_classes_api.py` | `organizer-fsi` ändert den Kurztext in `live` (200, `rev + 1`, Revision `text`, `public_seq + 1`); ändert `startsAt` (409 `field_locked`); `editor` ändert `startsAt` (200, `public_seq + 1`); Titel `[ABGESAGT] ...` in `live` 422 `title_has_status`; neuer Host in `descriptionMd` ist für `organizer` gesperrt, für `editor` erlaubt, bekannter Host nicht; `in_review`: `approver` korrigiert Text, `organizer` nicht, kritische Felder nie; `approved`, `followup`, `archived`, `withdrawn` alles 409; gemischte Felder alles oder nichts; Liste "Nachträglich geändert" und Gesehen |
| `test_autosave.py` | **Autosave-409:** `PUT` mit veraltetem `If-Match` → 409 `conflict` mit `current`; `PUT` erzeugt keine Revision, kein `rev`, kein `public_seq`, kein Audit; `PUT` kritischer Felder in `live` 409 `field_locked`; `GET`/`DELETE` nur die eigene Zeile; fremder Entwurf unsichtbar (auch für `admin`); erfolgreiches `PATCH` löscht den Entwurf; 428 ohne `If-Match`; 413 über 64 KiB; `If-Match` und Body-`rev` verschieden → 422; ETag-Header auf jeder Event-Antwort |
| `test_actions.py` | `cancel`, `postpone` (mit/ohne neuen Termin, Rechte), `reinstate` (Guards), Pflichtgrund, Grund nie im Audit und nie im Feed, `publicReasonText` nur mit `event.approve`, `public_seq`, Zustand `live` erforderlich, `assign-organization` (nur Redaktion, nur ohne Org), `revert-revision` (Inhaltsfelder, `revert_poster_replaced`, neue Revision), Alias `/image-exception` |
| `test_proposals.py` | Quote 5 (der sechste 422, zwei parallele sechste: genau einer gewinnt), Zurückziehen (T11), `member` kann nicht `PATCH`en oder feuern außer T11, Redaktion bearbeitet und weist zu, danach T01 möglich |
| `test_board_api.py`, `test_tasks_api.py`, `test_revisions_api.py` | `view=board` (Spalten, `moves`, `blockers`, `truncated`), Filter `organization`, `category` (Eltern), `mine`, `q`, `from`/`to` in Berliner Zeit, Sortierung je Spalte, Partner sieht fremde Org nie; Aufgaben je Rolle; Revisionen und Detail inkl. 404 |
| `tests/integration/pipeline/test_advance_states.py` | Worker gegen echtes Postgres mit fester Uhr: `publish_at` fällig → `live`; Poster inzwischen nicht mehr gültig → `blocked`, Zustand bleibt (**keine Umgehung**); ohne menschliche Freigabe nie; T08/T08b/T09b an der Grenze; zweiter Lauf ändert nichts; paralleler Mensch gewinnt (`skipped`); ein kaputtes Dossier stoppt den Lauf nicht; `purge_drafts` |
| `test_db_nets.py` (erweitert) | Direkt-SQL `approved`/`live` ohne Bild bleibt 23514 (alle Pfade: UPDATE `state`, UPDATE `hero_attachment_id`, INSERT); `persons_depicted` ohne `consent_note` macht `attachment_poster_ok` falsch; `events_public` liest `editor_draft` nicht; `events_app` darf `DELETE` auf `editor_draft`, nicht auf `event` |
| `tests/integration/publicapi/test_public_feed.py` (erweitert) | **Absage bleibt im Feed:** nach `cancel` liefert der Feed das Event mit `status: "cancelled"` und `statusReason`; `postponed` ebenso; T07 nimmt es heraus; privater Ort ergibt `venueText = null`; Kanarienvogel (`note`, Grund, `image_exception`) bleibt draußen; Schema `feed-v2.json` grün |
| `test_migrations.py` | ein Head `0004_pipeline_full`; frische DB gleich M3-Upgrade |
| `test_seed_dev.py` | neue `stage`-Werte, Idempotenz |

**Coverage (`scripts/coverage_critical.py`):** 100 % Zeilen und Branches für `app/modules/pipeline/**` (einschließlich `guards/`, `fieldclass.py`, `advance.py`, Aktionen, Zuweisung, Zurücksetzen), `audit`, `auth`, `publicapi`; Gesamt-Gate 90 % bleibt (Anhebung auf 97 % bis M5). Der Vollmatrix-Test und die Hypothesis-Maschine gelten als Teil der Abdeckung, keine Datei steht auf `EXEMPT`.

### 9.3 Frontend, Jest (`npm test`, Schwellen unverändert 97/94/97/98)

Je neue oder geänderte Komponente und je Service eine Spec mit `jest-axe` ohne Verstoß (Kontrast prüft Jest nicht, das übernimmt 9.4): `pipeline-board` (Drop-Prädikat nach `moves`, Zurückspringen, Tastatur-Sequenzen Leertaste, Pfeile, Enter, Escape mit Live-Region, Firefox-Leertaste wie Upstream, Phone-Tabs, Long-Press-Menü), `board-card`, `pipeline-page` (URL-Filter, 60-s-Aktualisierung mit Fake-Timern, 422- und 409-Behandlung, I13-Öffnung je Übergang, T01 direkt), `filters`, `dossier-list` (Split, Fokusrückgabe), `new-event-dialog` (Vorschlag ohne Org, Quote, Fehlertexte), `head` (Menüs je `allowedTransitions` und `allowedActions`, primärer Knopf je Zustand), `overview`, `form` (Sperrhinweise je `lockReason`, Feldklassen), `autosave` (15-s-Takt, Wiederholung, Offline-Puffer und Senden bei `online`, Wiederherstellen beim Öffnen, 409 öffnet den Dialog, 30-min-Ruhe nur in `idea`/`planning`), `conflict-dialog`, `history`, `transition-dialog` (Pflichtnotiz je T03/T06/T07/T10/T11, Warnungen mit Häkchen, `publishAt`, "Sofort" mit T05-Folgeaufruf, Vier-Augen-Hinweis, 403/409/422), `cancel-dialog` (Felder je Recht, Fehler), `image-exception-dialog`, `tasks` und `task-section`, `pending-changes.guard`, `EventsApi` (ETag/`If-Match`, Entwurf, Aktionen, Board), Konstanten-Test für 14 Ids.

### 9.4 Frontend, Playwright (`frontend/e2e/m3.spec.ts`, Browser aus nixpkgs wie M1)

Serieller Lauf, Nutzer aus dem Dev-Realm (`organizer-fsi`, `editor`, `approver-stupa`, `approver2-stupa`, `member`):

1. **Board per Tastatur:** `organizer-fsi` legt ein Dossier an; auf `/pipeline` Fokus auf die Karte, Leertaste, Pfeil rechts, Leertaste: die Karte steht in "Planung" (Server-Zustand `planning`, Live-Region "nach Planung verschoben"); Escape legt zurück; ein Drop in eine unmögliche Spalte meldet "nicht möglich"; Karte in "Freigabe" mit fehlenden Pflichtfeldern öffnet I13 mit "Fehlt noch" und deaktiviertem Knopf.
2. **Handy:** Viewport 390×844, Tabs und Wischen (Scroll des Pagers), Long-Press öffnet "Verschieben".
3. **Vier-Augen:** `approver-stupa` legt in `stupa` an, reicht ein, I13 zeigt den Hinweis und der Knopf ist gesperrt, `POST T04` per API ergibt 403 `four_eyes`; `approver2-stupa` gibt frei.
4. **Feldklassen in `live`:** `organizer-fsi` korrigiert den Kurztext (gespeichert), die Zeit-Felder sind gesperrt mit dem Hinweis, `PATCH startsAt` per API 409; `editor` sieht den Eintrag unter "Nachträglich geändert", setzt zurück (Kurztext wie vorher) und ändert die Uhrzeit.
5. **Absage bleibt im Feed:** `organizer-fsi` sagt über I14 ab; `GET /api/public/feed/events` enthält das Event mit `status: "cancelled"`; die Karte zeigt "Abgesagt" als Text; `editor` nimmt die Absage über "Mehr" zurück.
6. **Autosave überlebt Reload:** im Zustand `planning` Kurztext tippen, auf "Gespeichert" warten (<= 20 s, Anzeige), ohne "Speichern" neu laden: der Text steht mit dem Hinweis "Entwurf wiederhergestellt"; Konflikt: zweiter Browserkontext speichert, der erste bekommt beim nächsten Autosave den Konfliktdialog mit drei Spalten.
7. **Vorschlag:** `member` legt über I05 einen Vorschlag an (kein Organisationsfeld), sieht ihn unter "Meine Dossiers"; `editor` weist ihn zu; `member` sieht ihn danach nicht mehr.
8. **axe, Hell und Dunkel, am Produktions-Build:** `@axe-core/playwright` (neue devDependency, Version vor dem Einbau auf mindestens zwei Wochen Alter prüfen und exakt pinnen) gegen `http://127.0.0.1:8081` (Compose-`web`, Produktions-Build, kein `ng serve`), je einmal mit `data-theme="light"` und `"dark"` auf `/aufgaben`, `/pipeline` (Desktop und Handy), `/dossiers`, `/dossiers/:id` in `planning`, `in_review` und `live`, und mit geöffneten Dialogen I05, I13, I14, I15 sowie dem Konfliktdialog. Erwartung: 0 Verstöße der Schwere `serious` und `critical`, **Kontrast eingeschlossen**.

Hilfsfunktionen in `e2e/support/{dossier.ts, session.ts, axe.ts}` (erweitert); `m1.spec.ts` und `m2.spec.ts` laufen unverändert weiter (der M1-Pfad `/image-exception` und die M1-UI-Texte bleiben).

### 9.5 Gates (wie M2)

`uv run ruff check .`, `ruff format --check .`, `uv run basedpyright` (0 Fehler), `uv run pytest -m 'not integration and not e2e and not live'`, `uv run pytest -m integration`, `PROVENANCE_STRICT=1 uv run pytest --cov` samt `python -m scripts.coverage_critical`, `uv run alembic heads` (ein Head), `npm run lint`, `npm run typecheck`, `npm test` mit Coverage-Schwellen, `npm run build`, Prettier über alle neuen Frontend-Dateien (M2-Rest "Offen"), `deploy/compose-lint.sh`, `deploy/smoke.sh`, Playwright `m1`, `m2`, `m3`, `gitleaks detect`.

## 10. Abnahme M3

### 10.1 Kriterium wörtlich (PLAN §16.1, Zeile M3, Spalte "Fertig wenn …")

> Vollmatrix Zustand × Übergang × Rolle × Bild × Vier-Augen grün; U-GUARD-01 bis 13 grün; Property-Test "kein `live` ohne Bild" grün; trusted Approver kann eigenes eingereichtes Event nicht freigeben; Organisator:in korrigiert Kurztext in `live`, Uhrzeit nur über Redaktion; Absage bleibt im Feed als `cancelled`; Board per Tastatur bedienbar, axe grün, Hell und Dunkel am Produktions-Build geprüft; Autosave überlebt Reload; 100 % Branch `pipeline`

Lokale Lesart (wie M1 und M2, Keycloak statt Authentik): "Organisator:in" ist `organizer-fsi`, "Redaktion" ist `editor`, "trusted Approver" ist `approver-stupa` (die Organisation `stupa` ist die einzige vertraute), die zweite Person der Organisation ist `approver2-stupa`; "im Feed" heißt `GET /api/public/feed/events`; "Produktions-Build" heißt der Angular-Build im `web`-Container des Dev-Compose auf `127.0.0.1:8081`, nicht `ng serve`; "Autosave überlebt Reload" heißt: Eingabe, Wartezeit bis zur Anzeige "Gespeichert", Seite neu laden, Text steht wieder im Feld.

### 10.2 Prüfpunkte

1. **Vollmatrix** `test_transitions_matrix.py` gegen das Orakel `oracle.py` (9.1): grün, 14 Übergänge, alle Akteure. Dazu `tests/integration/events/test_rbac_matrix.py` (jeder Übergang und jede Aktion über die API, exakte Statuscodes).
2. **U-GUARD-01 bis 13** unter den Namen aus 9.1, grün (unit und integration).
3. **Property-Test** `test_publish_property.py` grün, unter anderem mit 200 Beispielen je Lauf und den neuen Regeln (keine Folge erreicht `approved`/`live` ohne Bild oder gültige Ausnahme; nie `live` ohne menschliche Freigabe).
4. **Vier-Augen:** `test_four_eyes.py` grün: `approver-stupa` feuert T04 auf die eigene Einreichung und bekommt 403 `four_eyes`; `approver2-stupa` gibt frei; der Direkt-INSERT wird vom CHECK abgewiesen.
5. **Feldklassen:** `test_field_classes_api.py` grün; im Browser (9.4 Szenario 4) korrigiert `organizer-fsi` den Kurztext in `live`, die Uhrzeit ändert nur `editor`.
6. **Absage im Feed:** `test_public_feed.py` und 9.4 Szenario 5: nach `cancel` steht das Event mit `status: "cancelled"` im Feed, die Karte zeigt "Abgesagt".
7. **Board per Tastatur, Handy-Tabs:** 9.4 Szenarien 1 und 2 sowie die Jest-Specs von `pipeline-board`.
8. **axe, Hell und Dunkel, Produktions-Build:** 9.4 Szenario 8, 0 Verstöße `serious`/`critical`.
9. **Autosave überlebt Reload; Konflikt zeigt Dreiwege-Dialog:** 9.4 Szenario 6 und `test_autosave.py`.
10. **100 % Branch `pipeline`:** `python -m scripts.coverage_critical` meldet "ok (0 file(s) below 100 %)", Gesamt-Coverage >= 90 %.
11. **Worker:** `test_advance_states.py` grün; im Dev-Stack nach `systemctl --user restart stupa-api stupa-worker` ein Dossier mit `publish_at` in einer Minute: nach höchstens 15 Minuten ist es `live` (Log `published=1`), ohne Poster bleibt es `approved` (Log `advance_blocked ... image_required`).
12. **Migration und Reste:** `alembic heads` genau `0004_pipeline_full`; `alembic upgrade head` auf frischer DB und auf M2-Stand grün; `psql -f deploy/db/roles.sql`; `test_db_grants*` grün; `seed_dev` zweimal ohne Neuanlage.
13. **Gates wie 9.5**, zusätzlich Playwright `m1.spec.ts` und `m2.spec.ts` unverändert grün (M1-Alias `/image-exception`, M1-Texte), `m1_acceptance.py` und `m2_acceptance.py` grün (die Teilmenge-Vergleiche der Antworten bleiben gültig, `EventOut` wächst nur additiv).

### 10.3 `backend/scripts/m3_acceptance.py`

Echter OIDC-Flow gegen den Dev-Keycloak wie `m1_acceptance.py`/`m2_acceptance.py` (gemeinsame Hilfen in `acceptance_common.py`): (a) `organizer-fsi` legt an, plant (T01), ergänzt Pflichtfelder, lädt ein Poster (Worker scannt und leitet ab), reicht ein (T02); (b) `approver-stupa`-Dossier der Org `stupa`: T04 → 403 `four_eyes`, `approver2-stupa`: T04 → 200, T05 → 200; (c) `editor` gibt das FSI-Dossier frei und veröffentlicht; (d) `organizer-fsi` ändert den Kurztext (200) und `startsAt` (409 `field_locked`), `editor` ändert `startsAt` (200); (e) `organizer-fsi` sagt ab, der Feed führt `cancelled`; `editor` nimmt zurück; (f) `member` legt einen Vorschlag an, der sechste Versuch (nach fünf offenen) ist 422 `proposal_quota_exceeded`; (g) Autosave: `PUT draft`, Reload per `GET draft`, `PATCH` räumt ab; (h) T03/T06/T07 mit Notiz, T11/T12; (i) ein Dossier mit gültigem Poster über die API bis T04 mit `publishAt` zwei Minuten in der Zukunft bringen (kein SQL-Eingriff), den nächsten Worker-Lauf abwarten und `live` prüfen; (j) Direkt-SQL `UPDATE event SET state='live'` ohne Bild scheitert mit `23514`. Ausgabe "M3 acceptance: all checks passed".

### 10.4 Abnahmeprotokoll

`docs/M3-ABNAHME.md` im Format von `M2-ABNAHME.md` (Ergebnistabelle zum Kriterium, Befehle mit gekürzter Ausgabe, Integrationslauf, "Offen"). Schritte vor dem Lauf: `uv run alembic upgrade head`; `psql -f deploy/db/roles.sql`; Realm-Synchronisierung für `approver2-stupa` (`scripts/keycloak_admin.py`); `uv run python -m scripts.seed_dev`; `systemctl --user restart stupa-api stupa-worker` (fehlen die Units, wie in `M2-ABNAHME.md` Abschnitt I mit `systemd-run --user` starten); `ng serve :4200` für die Dev-Specs; für axe `docker compose -f deploy/docker-compose.yml --env-file deploy/.env.dev up -d --build web`. Reste in der Dev-DB (Testdossiers, `e2e-*`-Kategorien, Sitzungen aus M2) bleiben; die E2E-Specs arbeiten mit zeitgestempelten Titeln und hängen von keinem Bestand ab. NixOS: `ruff` und `basedpyright` über `nix run nixpkgs#…`, `pytest` mit `LD_LIBRARY_PATH` für `libstdc++` und `libmagic`, Playwright mit `PLAYWRIGHT_BROWSERS_PATH=$(nix build --no-link --print-out-paths nixpkgs#playwright-driver.browsers)`.

## 11. Entscheidungen für Luis (Vorschläge, nicht belegt)

Der Kontrakt arbeitet mit der **fett** markierten Voreinstellung, bis Luis anders entscheidet.

| # | Frage | Voreinstellung | Alternative / Folge |
|---|---|---|---|
| D1 | HTTP-Status von `four_eyes` | **403** `four_eyes` mit `reasons[]` (Auftrag), vor allen anderen Guards ausgewertet | 422 wie die übrigen Guards (M1 4.1 führte `four_eyes` unter den 422-Codes); 403 ist klarer ("diese Person darf nicht"), 422 einheitlicher |
| D2 | Recht für T10 und T12 (nur Redaktion) | **neues Recht `event.restore`** nur bei `editor` (Katalog 5.3 nennt keines) | `event.assign_org` mitbenutzen (gleicher Personenkreis, aber falscher Name); M2 D7 lehnte ein neues Recht für `trusted` ab, hier gibt es keinen vorhandenen passenden Namen |
| D3 | `note` und `reason` | **ein Feld `note`**, bei fünf Übergängen und allen Aktionen (`reason`) Pflicht; eine Spalte `event_status_event.note` | zwei Felder (frei, Pflicht) bräuchten zwei Spalten |
| D4 | Wirksamwerden des Entwurfs nach 30 Minuten Ruhe (E21) | **durch den Client**; der Server hält Entwürfe 14 Tage | Server-Job `apply_idle_drafts`: bräuchte Rechteprüfung ohne Request (Principal aus der Sitzung wiederherstellen) und erzeugt Revisionen ohne Zutun der Person |
| D5 | T04 "Veröffentlichen am (leer = sofort)" | **Client-Folge:** leer heißt "Sofort veröffentlichen" an, der Dialog feuert nach T04 selbst T05; der Worker veröffentlicht nur mit gesetztem `publish_at` | Server veröffentlicht `approved` ohne `publish_at` beim nächsten Lauf (bricht das manuelle T05 aus M1/E2E, bis zu 15 Minuten Wartezeit); oder T04 und T05 in einem Aufruf |
| D6 | Wann `cancel`/`postpone`/`reinstate`? | **nur in `live`** (öffentlich sichtbar); vorher T11/T06 | auch in `approved`; dann geht ein bereits abgesagtes Event bei `publish_at` live |
| D7 | Leserecht der vorschlagenden Person nach `assign_organization` | **endet** (sie ist nicht in der Org; M2-Abnahme prüft, dass Entzug 404 ergibt) | Ersteller bleibt Leser mit `created_by`: bricht die M2-Aussage "404 nach Entzug der Gruppe" für Dossiers, die die Person selbst angelegt hat |
| D8 | Verantwortliche Person auf der Karte | **Avatar der erstellenden Person**; `owner_id` kommt mit M4 (Aufgaben zuweisen, Mitgliederliste aus `membership`) | `owner_id` und Personenauswahl schon in M3 |
| D9 | `postpone` mit neuem Termin | **Status bleibt `postponed`**, bis `reinstate` ("Termin steht") bestätigt; Termin wird geändert und `public_seq + 1` | Status springt auf `scheduled` mit neuem Datum: einfacher, aber "Verschoben" verschwindet für Abonnent:innen sofort |
| D10 | Zusatzguards für Sys-T05 | **`dateInFuture` und `humanApproval`** | nur `publishAtReached`; ein verpasster Termin würde nachträglich veröffentlicht |
| D11 | `fourEyes` bei T05 (PLAN: "alle T04-Guards erneut") | **nicht wiederholt**: T04 hat die zweite Person schon erzwungen (CHECK) | wiederholen: die einreichende Person könnte ihr eigenes, von anderen freigegebenes Event nicht veröffentlichen |
| D12 | `GET /events`: Antwortform | **schlanke `EventCard`** (kein `descriptionMd`), Filter `organization` und `category` als Slug, `organizationId` entfällt | `Page<EventOut>` behalten: Board mit 200 Karten trägt dann bis 4 MB Beschreibungstext |
| D13 | Zwei Aktionen über die Auftragsliste hinaus | **`acknowledge-changes`** ("Gesehen" in der Liste Nachträglich geändert) und **`confirm-flyer`** (Guard `flyer_date`, Knopf "Flyer geprüft") | ohne beide bleibt die Liste ewig voll bzw. `flyer_date` ist nicht auflösbar (Guard dann Platzhalter bis M4) |
| D14 | `venue_id` und Ortsauswahl (M2 D4 verschoben auf M3) | **in M3** (Spalte, `VenueRef` im Dossier, View, Auswahl im Formular) | auf M4: dann bleibt `venue_missing` bei Freitext, die 44 Orte aus M2 sind ungenutzt |
| D15 | Wer legt Vorschläge an | **jede angemeldete Person** (auch `viewer`, `nobody`), 5 offene je Person (E09) | nur `member` ohne Org-Rolle: ein `viewer` müsste erst Gruppen verlieren |
| D16 | Bearbeiten in `approved` | **gesperrt** (PLAN 4.1); Änderung über T06 | Prüfende dürfen wie in `in_review` Text korrigieren |
| D17 | Minimaler Tab "Verlauf" schon in M3 | **ja**, nur Revisionsliste mit "Zurücksetzen" (Voraussetzung für `revert_revision`) | I12 komplett in M4, bis dahin Zurücksetzen nur per API |

## 12. Abweichungen vom PLAN und von M1/M2 (zur Nachführung durch Luis)

1. **`four_eyes` ist 403, nicht 422** (M1 4.1 zählte es zu den Guard-Codes mit 422). Begründung D1.
2. **Auswertungsreihenfolge:** Recht, Zustand, Pflichtnotiz, `fourEyes`, übrige Guards; die Reihenfolge der `reasons[]` ist die Tabelle 2.3 (M1 nannte `field_missing, start_in_past, image_required, four_eyes`; `venue_missing` ersetzt `field_missing` mit `field=venueText`). Neue Codes außerhalb PLAN 4.4: `publish_at_not_reached`, `not_human_approved`, `not_ended_yet`, `origin_kind_mismatch`, `retrospective_missing`, `outcome_missing`, `howto_unverified`, `followup_not_due`, `open_comment_required`; PLAN 4.4 führt `rights_incomplete` mit Credit und Rechtegrundlage, hier bleiben beide in `image_required` (gleich streng wie der Trigger, M1), `rights_incomplete` prüft allein die Einwilligung.
3. **`event_status_event`:** Spalten `four_eyes` und `submitted_by` statt `via_org_role` (PLAN 3.3): der Name gilt auch für `admin` und die Redaktion mit `EDITOR_FOUR_EYES`, und ein CHECK kann `submitted_by` einer anderen Tabelle nicht lesen.
4. **T05:** `fourEyes` wird nicht wiederholt (D11); `dateInFuture` bindet nur Sys-T05 (M1-Abweichung 8 bleibt für Menschen); `publishAtReached` bindet nur Sys (ein Mensch darf früher veröffentlichen).
5. **`attachment_poster_ok`** (SQL) bekommt die Einwilligungsregel; `PosterSnapshot.usable` bleibt wie M1.
6. **Poster in `approved`/`live` ersetzen** ist nicht Teil von M3 (E07 nennt das Poster kritisch, ein Austausch verlangt das verzögerte Umhängen von `hero_attachment_id` nach Scan und Derivaten; das gehört mit "Ersetzen" zu M4/I08). In M3 bleibt es 409 `field_locked`; wer ein anderes Poster braucht, nimmt T07 oder T06.
7. **Autosave:** Tabelle heißt `editor_draft` (E21), nicht `event_draft`; das Wirksamwerden nach 30 Minuten Ruhe führt der Client aus (D4), nicht der Server. `PUT/GET/DELETE /draft` und `GET /revisions/{rev}` sind Routen über die Auftragsliste hinaus.
8. **Ein Feld `note`** statt `note` und `reason` (D3).
9. **I04:** kein Kalender-Umschalter (`app-calendar-grid` gehört zu M5); **I03:** kein Format-Filter (M5); **I05:** kein "Aus Vorlage"/"Instagram-Post" (M5/M6).
10. **Gate-Regel (M2) mit zwei Ausnahmen** (`POST /events`, `POST .../transitions/{T}` nur Session-Gate, Entscheidung im Service). Folge für die M2-Matrix: `member`, `nobody`, `viewer` legen ohne Org einen Vorschlag an (201), die Übergangsroute antwortet auf fremde Dossiers 404 und auf sichtbare ohne Recht 403.
11. **`GET /api/events`:** `EventCard` statt `EventOut`; Parameter `organization` (Slug) ersetzt `organizationId`; neue Parameter `view, category, mine, from, to, sort, columnLimit`. `EventOut` wächst additiv.
12. **Neues Recht `event.restore`** (nur `editor`) für T10 und T12 (D2).
13. **Zusätzliche Aktionen** `acknowledge-changes` und `confirm-flyer` (D13).
14. **`cancel`/`postpone`/`reinstate` nur in `live`; `postpone` mit Termin lässt den Status `postponed`** (D6, D9).
15. **Feed:** `statusReason` und der Ort aus `venue` kommen additiv in `PublicEventOut` und die View; die Feed-Hülle bleibt die M1-Form (M1-Abweichung 1).
16. **T08** gilt für `origin_kind IN (internal, mcp)` (das Komplement von T08b; PLAN nennt nur `<> imported`); `owner_id` entfällt in M3 (D8).
17. **T04 ohne `publishAt`** hält das Dossier in `approved` bis zu einem menschlichen T05; der Dialog hängt T05 selbst an (D5).
18. **Platzhalter-Guards** (`checklistDone`, `factsValid`, `noOpenDuplicate`, `noOpenCommentOnField`, `openCommentRequired`, `locationConfirmed`, Zeitzonen-Warnungen, Nachbereitungs-Guards) melden in M3 "erfüllt": die Guard-Funktionen sind getestet, ihre Datenquelle kommt mit M4 bis M6. Bis dahin sind T02/T09 weniger streng als im Endausbau; die Abnahme führt das auf.
19. **Minimaler Tab "Verlauf"** vor I12 (D17), **`location_precision`** bleibt M1-Abweichung 4 (vor Pilot M5).
20. **Löschkonzept:** `event_status_event.note` und `editor_draft.fields` enthalten Freitext; wie M1-Abweichung 9 gehört beides vor Stufe B in das Löschkonzept (8.9). Entwürfe sind durch die 14-Tage-Bereinigung begrenzt.
21. **Integrationslauf (Erweiterung):** Karten (`EventCard.blockers`) rechnen mit demselben vollen Snapshot wie `GET /guards/{T}` (Anhänge in Quarantäne, Eintritt in `followup`, Poster aus einem anderen Jahr), gebündelt in `events/card_extras.py` mit drei gruppierten Abfragen je Seite (`test_card_guards.py`). `m3_acceptance.py` führt den Worker in (i) ohne Warten auf die Viertelstunde einmal von Hand aus (arq-Job `advance_states` am laufenden Worker, `M3_WAIT_CRON=1` wartet wie bisher) und prüft zusätzlich (k) `publish_at` per SQL in die Vergangenheit, ein Lauf, `live` und im Feed; (l) Ende per SQL 13 Stunden zurück, ein Lauf, `followup`; dazu in (e) `reinstate` zurück auf `scheduled` im Feed und in (g) `PUT draft` und `PATCH` auf veraltetem `If-Match` mit 409 `conflict` samt `current`. SQL verschiebt dabei nur Datumsspalten, nie den Zustand.
22. **Review-Runde (18.10.):** `revert_revision` ist in `in_review` und `approved` gesperrt (409 `field_locked`), `plan_patch.locked` gilt auch dort; die Guard-Schnappschüsse für `PATCH`, `postpone` und `revert` rechnen das Poster-Jahr mit dem neuen Starttermin (`guard_snapshot(starts_at=)`). `postpone` mit Termin und jede Textänderung an `summary` in `live` laufen durch `enforce_live`. T04 prüft `hasField` der T02-Menge erneut (ein Prüfender kann `summary` in `in_review` leeren).
23. **`If-Match` ist Pflicht (428)** bei T04, T05, `cancel`, `postpone`, `reinstate` und `revert-revision`; `*` zählt nicht. Die anderen Übergänge und Aktionen behalten das optionale `If-Match` (Abschnitt 4.2).
24. **Link-Hosts (E07, A04):** `link_hosts` zählt jedes `scheme://`, `//host`, `www.` und `domain.tld`; Userinfo und Port fallen weg. Der M5-Sanitizer muss alles andere mit Ziel (`javascript:`, `data:`) entfernen.
25. **`allowedActions`** enthält zusätzlich `postpone-with-date` und `public-text` (Hinweise für den Absagen-Dialog, keine eigenen Routen). `GET /revisions` hat den Parameter `minRev`; `changeNote` und die Snapshot-Felder `imageException`, `createdBy`, `submittedBy`, `approvedBy` liefert die API nur an Personen mit `event.edit` in der Organisation.
26. **Entwurfs-Body:** 413 kommt aus einer Route-Klasse, die den Body streamt und bei 64 KiB abbricht (auch ohne `Content-Length`). Der Autosave wiederholt nur bei Netz- und 5xx-Fehlern, bei 4xx hält er an (Status `error`). Vor einem Übergang speichert die Seite nur in `idea` und `planning`.

## 13. Verzeichnisbesitz

Zwei Builder, beide schreiben nur in ihren Bereich. Konflikte löst die Orchestrierung. Kopien aus Upstream mit Kopf `Copied from STUPA-Workflow@93c33d6 <pfad>` (oder "Pattern from" für Nachbauten) und Eintrag in `PROVENANCE.json` (Modus `U`); nichts wird übernommen, ohne dass der Builder die Quelle gelesen hat. Kein Commit und kein Push vor dem Review; im letzten Schritt entsteht `feat/m3-pipeline` mit gescopten Commits (`feat(pipeline)`, `feat(events)`, `feat(worker)`, `feat(frontend)`, `test`, `docs`). Kein Eingriff in Live-Systeme.

| Builder | Besitzt | Aufgaben |
|---|---|---|
| **backend** | `backend/**` | Migration `0004_pipeline_full`; `app/modules/pipeline/**` (`transitions.py`, `decision.py`, `guards/`, `fieldclass.py`, `advance.py`, `actions_service.py` für Absage/Verschieben/Wiedereinsetzen, `assign.py`, `revert.py`, `snapshot.py`, `reasons.py`, `service.py` mit `stage_system_fire`, `router.py`, `actions_router.py`); `app/modules/events/**` (`models.py`, `schemas.py`, `service.py`, `patch.py`, `drafts.py`, `board.py`, `cards.py`, `revisions.py`, `access.py`, `presenter.py`, `router.py`, `drafts_router.py`, `revisions_router.py`); neues Modul `app/modules/tasks/` (`service.py`, `router.py`, `schemas.py`); `app/modules/publicapi/**` (`statusReason`, Ort); `app/modules/dossier/**` (Poster-Felder `personsDepicted`, `consentNote`, `409 quarantined`); `app/shared/permissions.py` (`event.restore`); `audit/actions.py` (`EVENT_CANCEL`, `EVENT_POSTPONE`, `EVENT_REINSTATE`, `EVENT_ASSIGN_ORG`, `EVENT_REVERT`, `EVENT_ACK_CHANGES`, `EVENT_FLYER_CONFIRM`); `api_routers.py`; `worker/{advance.py,main.py}`; `tests/**` inklusive Harness (`approver2-stupa`), `scripts/{seed_dev.py,m3_acceptance.py,coverage_critical.py}`, `seeds/dev_events.yaml`, `tests/schema/feed-v2.json` |
| **backend** (außerhalb `backend/`, nur diese Dateien) | `deploy/db/roles.sql` (`editor_draft` mit `DELETE`), `deploy/keycloak/stupa-events-realm.json` (`approver2-stupa`, Gruppe `events-stupa-approver`), `docs/M3-ABNAHME.md`, `.claude/skills/be-pipeline/SKILL.md` und `be-events/SKILL.md`, `CLAUDE.md`, `README.md` | Skill `be-pipeline` auf 14 Übergänge, Guards, Aktionen, Worker; `CLAUDE.md` nennt `M3-KONTRAKT.md`; README: neue Nutzer, Routen, Worker-Cron |
| **frontend** | `frontend/**` | alles aus Abschnitt 8, `frontend/e2e/{m3.spec.ts,support/**}`, neue devDependency `@axe-core/playwright`, `PROVENANCE.json`-Einträge der Kopien, `.claude/skills/frontend/SKILL.md` |

Schnittstellen: Die Typen aus Abschnitt 5.1 und die Tabellen aus 2.2 bis 2.4 sind der gemeinsame Vertrag. Reihenfolge: Das Backend liefert zuerst Migration, `EventOut`/`EventCard`/`BoardOut`, Übergänge und Aktionen (Abschnitte 2, 5.2 bis 5.4) mit den Realm-Nutzern, danach Entwurf, Revisionen, Aufgaben und Worker; das Frontend baut gegen den laufenden Dev-Stack und gegen `HttpTestingController`-Antworten und beginnt mit den Bausteinen aus 8.2. Keine Datei in `.github/**` ändert sich; CI ruft `npm run typecheck`, `npm test` und die bestehenden Jobs auf (der Playwright-Lauf mit axe bleibt wie M1/M2 ein manuelles Gate gegen den Dev-Stack).
