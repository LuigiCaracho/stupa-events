# M4-Kontrakt: Dossier und Wissen

Verbindlich für die drei Builder von M4 (**backend-dossier**, **backend-mail**, **frontend**). Quellen: `PLAN.md` §3.3 (`attachment`, `document`, `document_revision`, `checklist_item`, `comment`, `notification`, `notification_pref`, `media_ref`), §3.4, §3.5, §4.4, §5.4, §7 komplett, §9.4, §15.1 (I08 bis I12, I27, I28), §16.1 (Zeile M4), §18 Minor 4, Entscheidungslog E12, E20, E21, E27, `ENTSCHEIDUNGEN.md`, `docs/M1-KONTRAKT.md` bis `docs/M3-KONTRAKT.md` (gelten weiter, ihre Abweichungslisten ebenso), `docs/M3-ABNAHME.md` Abschnitt "Offen", `CLAUDE.md`, die Skills unter `.claude/skills/*`, Upstream `STUPA-Workflow@93c33d6` (U) für Muster (`U backend/app/modules/media/{router,service,refs}.py`, `U backend/app/modules/notifications/{models,service,recipients,templating,kinds,mail}.py`, `U backend/app/modules/applications/service/comments.py`, `U backend/app/modules/todos/lexorank.py`, `U frontend/src/app/shared/markdown/*`, `U frontend/src/app/shared/ui/{history,chat,file-drop-zone,image-thumb}`, `U frontend/src/app/pages/admin/mail-templates`, Kit-Sekundär-Entry `vendor/ui-kit/markdown-editor`). Pfade `U ...` sind relativ zu `upstream/STUPA-Workflow`.

Stand der Analyse: Branch `feat/m3-pipeline`, Arbeitsbaum ohne M4-Änderungen, Migrationen bis `0004_pipeline_full`. Der Branch `feat/m4-dossier` entsteht erst im letzten Schritt (nach Review); bis dahin kein Commit, kein Push. Wo dieser Kontrakt dem PLAN oder M1 bis M3 widerspricht, gewinnt der Kontrakt, die Abweichung steht in Abschnitt 10. Was nicht belegt ist, steht als Vorschlag in 10.2 und wartet auf Luis; die **fett** markierte Voreinstellung gilt, bis er anders entscheidet.

## 1. Lückenanalyse

Jede Zeile ist gegen den Code geprüft (Datei in Klammern), nicht gegen die Kontrakte.

### 1.1 Was schon existiert

| Teil | Stand | Beleg |
|---|---|---|
| Tabelle `attachment` mit `kind`, Scan-Status, Rechtespalten (`alt_text, credit, rights_basis, license_ref, source_url, persons_depicted, consent_note`), `visibility`, `meta`, `derivatives`, `supersedes_id`, `retired_at`, CHECK `size <= 10 MiB` | vorhanden, aber `kind`-Werte weichen ab (`poster_print, businessplan, mail_attachment`), kein CHECK "nie shared", ein Größenlimit für alles | `files/models.py`, `0002` |
| MIME-Sniff (libmagic), Endung-gegen-Inhalt-Prüfung, OOXML-Container-Prüfung | vorhanden; Allowlist enthält GIF, `.doc/.xls/.ppt`, `.md/.txt/.csv` fehlen | `files/mime.py` |
| `clean_image` (Pillow: Bombenschutz 40 MP, Neukodierung, kein EXIF, ICC-Limit) | vorhanden, wird nur vom Poster-Pfad aufgerufen | `media/images.py`, `dossier/posters.py` |
| ClamAV-Scan, Job `scan_attachment`, Retry, `error`-Endzustand, Löschen des Objekts bei Fund | vorhanden | `files/scanner.py`, `worker/scan.py` |
| Poster-Upload (`POST /api/events/{id}/poster`), Download (`GET .../poster`), Derivate `thumb_400, card_1200, og_1200x630` im Public-Bucket | vorhanden, nur Poster | `dossier/{posters,router,derive,worker_jobs}.py` |
| `content_disposition` (ASCII-Fallback plus `filename*`), `sanitize_display_name`, `sanitize_storage_name` | vorhanden | `shared/filenames.py` |
| Trigger `enforce_publish_image`, `keep_published_poster`, SQL-Funktion `attachment_poster_ok` (inkl. Einwilligung) | vorhanden | `0002`, `0004` |
| `Snapshot` mit `quarantined_attachments, open_hero_comments, open_required_checklist, open_comments (int or None), facts_error`, `PosterSnapshot` mit `consent_ok, reused_in_other_year` | vorhanden, alle bis auf `quarantined_attachments` und `reused_in_other_year` mit neutralem Standard | `pipeline/snapshot.py`, `events/card_extras.py` |
| Guards `open_comment_required` (blockt nur bei `== 0`), `no_open_comment_on_hero`, `checklist_done`, `rights_complete`, `attachments_scanned`, `flyer_date_confirmed` als getestete reine Funktionen; `FixAction.OPEN_COMMENT, OPEN_CHECKLIST, FILL_RIGHTS, CONFIRM_FLYER` | vorhanden, Datenquelle fehlt | `pipeline/guards/{content,media}.py`, `reasons.py` |
| Aktion `confirm-flyer` (setzt `event.flyer_checked_at`) | vorhanden | `pipeline/actions_service.py` (M3 12.13) |
| `editor_draft` mit `owner_kind` (CHECK nur `event`) und Primärschlüssel `(owner_kind, owner_id, principal_sub)`; "M4 hängt `document` an dieselbe Tabelle" | vorhanden, CHECK muss wachsen | `events/models.py`, M3 4.3 |
| `MarkdownImage` (Tabelle `markdown_image`), `MediaService.upload/open`, `media/refs.py` (`image_ids_in`) | vorhanden, **kein Router**, keine `media_ref`, kein GC | `media/*`, `api_routers.py` |
| Notifications-Gerüst: `MailMessage`, `CapturingMailSender`, `SmtpMailSender`, `ArqMailQueue`/`DirectMailQueue`, Sandbox-Rendering mit `StrictUndefined`, `kinds.py` mit drei Kinds (`status_update, task, comment`) | vorhanden, **ohne Tabellen, Router, Empfängerregeln, Templates** | `notifications/*`, `worker/mail.py` |
| Worker mit `advance_states`, `purge_drafts`, Audit-Cron, Scan, Mail, Derive | vorhanden, kein GC, keine Fälligkeitsmail | `worker/main.py` |
| Rechte `dossier.attach`, `comment.write`, `event.edit`, `event.submit`, `event.approve`, `dossier.read_restricted`, `event.read_all`, `library.read` samt Rollenzuordnung | vorhanden, reichen für M4 (kein neues Recht) | `shared/permissions.py` |
| Frontend: Dossier-Detail mit Kopf, Übersicht, Formular, Autosave, Konflikt, minimalem Verlauf (`dossier-history`), `app-poster-upload`, `app-file-drop-zone`, `app-image-thumb`, `app-guard-list`, Konto mit `session-section` | vorhanden | `frontend/src/app/features/**`, `shared/ui/**` |
| Kit-Sekundär-Entry `vendor/ui-kit/markdown-editor` (Tiptap) | im Submodul vorhanden, **nicht verdrahtet** (kein Pfad-Alias in `tsconfig.json`, kein Jest-Mapper) | `vendor/ui-kit/markdown-editor`, `tsconfig.json:18-22` |

### 1.2 Was fehlt

| # | Lücke | Wirkung | Abschnitt |
|---|---|---|---|
| H1 | Anhänge nur als Poster: keine Liste, kein Upload anderer Arten, kein Ersetzen im Zustand `approved`/`live` (M3 12.6), kein Ausblenden, keine Sichtbarkeit ändern, keine Vorschau | I08 nicht baubar | 2.1, 3, 5.1 |
| H2 | `kind`-Enum und Größenlimit passen nicht zu PLAN/E27; kein CHECK `quote/business_plan/contract` nie `shared` | Preise könnten `shared` werden | 2.1 |
| H3 | Keine Tabellen `document`, `document_revision`, `checklist_*`, `comment`, `quote`, `notification`, `notification_pref`, `media_ref` | M4-Kern fehlt | 2 |
| H4 | Media-Router (`/api/media/images`), `media_ref`, GC fehlen; Editor und Anleitung können keine Bilder einbetten | I09 ohne Bilder, Waisen sammeln sich | 2.7, 8 |
| H5 | Fünf Platzhalter-Guards (M3 12.18) lesen neutrale Standardwerte: `open_comments` bleibt `None`, `open_hero_comments`/`open_required_checklist` bleiben 0, `quarantined_attachments` zählt nur das Poster, `reused_in_other_year` ist immer `false` | T02, T03, T04 zu locker | 4 |
| H6 | `rights_complete` prüft nur die Einwilligung; Alt-Text, Credit und Rechtegrundlage stecken in `image_required` (M3 12.2) | Doppelmeldung, falscher Knopf | 4.3 |
| H7 | Keine In-App-Inbox, kein Empfängermodell, keine Mail-Templates (de), `NOTIFICATION_KINDS` passt nicht zu PLAN 9.4, kein `/api/account/notification-prefs`; Mailversand ohne Redis wird nicht bewusst verworfen | I27/I28 nicht baubar | 5.7 |
| H8 | Tiptap nicht verdrahtet, kein Roundtrip-Gate, kein Zeilen-Diff (Kit hat nur `app-config-diff`), keine `shared/markdown/*`-Kopien | E20-Gate fehlt | 6, 7 |
| H9 | Aufgaben (I02) kennen keine zugewiesenen Checklistenpunkte | PLAN 3.3 "Aufgabe" | 5.4 |
| H10 | EXIF-GPS-Befund (PLAN 18, Minor 4) nicht durch Test belegt; Dokumente (PDF, OOXML) behalten Metadaten | Datenschutz | 3.5 |
| H11 | Seeds für Checklisten-Vorlagen fehlen | Abnahme "Checkliste aus Kategorie-Vorlage" | 2.4 |

### 1.3 Was M4 nicht liefert (steht schon im PLAN bei M5 bis M8, B, D)

Archivansicht und Lesen fremder `shared`-Anhänge durch andere Organisationen (M5, Vorlagen-Suche), Klonen mit `carry_over`, Format-Master-Anleitung und `verified_at`-Pflege (T09, M5; die Spalten legt M4 an), Bibliothek `owner_kind = library` (M5/I19), interne Suche über Dokumente (M5), Digest-Mails (B), Push (B), Erwähnungen (`@`) und `comment_mention` (siehe 10), Dubletten/Importe (M6), Agent-Sitzungen (D). Der Tab "Anleitung" zeigt in M4 nur die Spalte "Diese Ausgabe"; "Format: Master-Anleitung" erscheint mit M5.

## 2. Datenmodell-Delta (Migration `0005_dossier_knowledge`)

Genau ein Head `0005_dossier_knowledge` (22 Zeichen), auf `0004_pipeline_full`. Frische DB und M3-Upgrade ergeben dieselben Zeilen (`test_migrations`). `models.py` wird mitgeführt. Alle Zeitspalten `timestamptz`, Standard `now()`. Bestandsdaten bleiben gültig: Datenschritte stehen vor den neuen CHECKs.

### 2.1 `attachment` (Änderung)

| Änderung | Regel |
|---|---|
| `kind` | CHECK neu: `poster, social_post, business_plan, quote, contract, howto_file, other`. Datenschritt: `businessplan` zu `business_plan`; `poster_print` und `mail_attachment` zu `other` (`poster_print`/`mail_attachment` aus PLAN 3.3 entfallen, Abweichung 10.1.1) |
| `visibility` | Datenschritt: Zeilen mit `quote/business_plan/contract` und `shared` zu `org`. Dann CHECK `ck_attachment_restricted_not_shared`: `kind NOT IN ('quote','business_plan','contract') OR visibility <> 'shared'`. Standard `org`; API setzt `shared` als Standard für `howto_file` (E12) |
| Größe | CHECK `size_limit` ersetzt durch `ck_attachment_size`: `(mime LIKE 'image/%' AND size_bytes <= 10485760) OR size_bytes <= 26214400` (E27: 10 MiB Bild, 25 MiB Dokument) |
| neu `contains_date boolean NOT NULL DEFAULT false`, `dated_for date` | PLAN 3.4 `poster {contains_date, dated_for}`; eine Spalte statt `meta`, damit der Flyer-Check in SQL und im Snapshot lesbar ist |
| neu `flyer_date_confirmed_at timestamptz`, `flyer_date_confirmed_by text` | gesetzt von der Aktion `confirm-flyer` am aktuellen Poster (zusätzlich zu `event.flyer_checked_at`, das die Quelle des Guards bleibt, 4.5) |
| neu `preview_key text` | Objektschlüssel der privaten WebP-Vorschau (400 px lange Kante) im Attachment-Bucket; vom Worker nach sauberem Scan für **jedes** Bild gesetzt (3.4) |
| Index | `ix_attachment_event_kind` auf `(event_id, kind) WHERE retired_at IS NULL` |
| schon vorhanden, unverändert | `alt_text, credit, rights_basis, license_ref, source_url, persons_depicted, consent_note, supersedes_id, retired_at, derivatives, meta` |
| Rechte | kein `DELETE` (E27, `test_db_grants`); `UPDATE` bleibt, der Trigger `keep_published_poster` bleibt |

`meta` je `kind` (Pydantic-Union, `extra=forbid`, PLAN 3.4): `poster {format ∈ a3|a4|1:1|4:5|9:16, width, height}`, `social_post {channel, account, captionMd, plannedFor, postedUrl, status ∈ draft|planned|posted}` (`planned` nur mit Bild, sonst 422 `social_post_needs_image`: "Kein Foto, kein Post."), `business_plan {version, totalCents, incomeCents}`, sonst `{note}`. Für `quote` bleibt `meta` leer (die Beträge liegen in der Tabelle `quote`, 2.6).

### 2.2 `document` und `document_revision` (neu)

`document`: `id uuid pk`, `event_id uuid NOT NULL` (FK `event.id` `RESTRICT`; M5 lockert das auf Besitzer `format`/`library`, Abweichung 10.1.10), `kind` CHECK `howto, retrospective, notes, mail_template`, `title text` (1 bis 200, ohne Steuerzeichen), `body_md text NOT NULL DEFAULT ''` (<= 200 000 Zeichen), `meta jsonb NOT NULL DEFAULT '{}'`, `visibility` CHECK `team, org, shared`, `carry_over boolean NOT NULL` (Standard `true`, `false` bei `retrospective`; steuert M5 "Neu aus Vorlage"), `rev integer NOT NULL DEFAULT 1`, `verified_at timestamptz`, `verified_by text` (von M4 nicht geschrieben, T09 in M5), `created_by text`, `created_at`, `updated_at`. Partieller Unique-Index: höchstens ein `howto` je Dossier. `kind = retrospective` steht im CHECK, wird in M4 aber nicht angelegt (Quelle bleibt `event.retrospective_md`, 10.1.9). Standard-`visibility`: `howto`, `mail_template` `shared`; `notes` `org` (E12). `meta` bei `mail_template`: `{subject, toHint, placeholders[]}` (`placeholders` berechnet der Server beim Speichern, 5.6).

`document_revision`: `document_id` (FK), `rev integer`, `title`, `body_md`, `meta jsonb`, `actor_id text`, `actor_type` CHECK `human, agent, system`, `change_note text` (<= 500), `at`, Primärschlüssel `(document_id, rev)`. Append-only (Trigger wie `event_revision`: `UPDATE`/`DELETE` verboten), `events_app` ohne `UPDATE`/`DELETE`. `document` selbst hält die jüngste Fassung (`body_md`, `rev`) als Kopie, geschrieben in derselben Transaktion wie die Revision.

`editor_draft`: CHECK `owner_kind IN ('event','document')`; für `document` ist `fields` `{bodyMd, title?}` (Autosave der Anleitung und Mailvorlage, 5.3).

### 2.3 `comment` (neu)

`id uuid pk`, `event_id` (FK `RESTRICT`), `parent_id` (FK `comment.id`, nur Wurzel darf Elternteil sein, im Service geprüft), `author_sub text`, `actor_type` CHECK `human, agent, system`, `body_md text` (1 bis 4000), `anchor jsonb` (NULL bei Antworten und allgemeinen Kommentaren), `resolved_at`, `resolved_by text`, `created_at`. CHECK `ck_comment_anchor`: `anchor IS NULL OR (jsonb_typeof(anchor) = 'object' AND (anchor ? 'field' OR anchor ? 'attachmentId' OR anchor ? 'checklistItemId' OR anchor ? 'documentId'))`. Der Anker ist `{field}` (`hero` oder ein Feldname aus `pipeline/guards/common.FIELD_NAMES`), `{attachmentId}`, `{checklistItemId}` oder `{documentId, rev, from, to}` (Zeichenoffsets in `body_md` der Revision `rev`, `from < to`). Die API prüft Form, Zugehörigkeit zum Dossier und Offsets; der CHECK ist das Netz. Index `ix_comment_open` auf `(event_id) WHERE resolved_at IS NULL AND parent_id IS NULL`. Trigger `comment_immutable`: erlaubt `UPDATE` nur auf `resolved_at, resolved_by`; `events_app` ohne `DELETE`. Kein Bearbeiten und kein Löschen (Verlauf bleibt prüfbar).

### 2.4 `checklist_template`, `checklist_template_item`, `checklist_item` (neu)

- `checklist_template(id, slug UNIQUE, name, category_id FK NULL, profile NULL CHECK generic|party|meeting|trip, CHECK num_nonnulls(category_id, profile) <= 1)`. Auflösung beim Anwenden: Vorlage der Hauptkategorie, sonst Vorlage des `required_profile` der Hauptkategorie, sonst `generic`.
- `checklist_template_item(id, template_id FK, key text, position int, text, phase CHECK planning|review|live|followup, required boolean, due_offset_days integer CHECK -365..365)`, `UNIQUE (template_id, key)`. Der Schlüssel `key` ist stabil, damit eine Änderung der Vorlage später zuordenbar bleibt.
- `checklist_item(id, event_id FK RESTRICT, template_item_id FK NULL, position text COLLATE "C", text (1 bis 200), phase, required, assignee_sub text, due_offset_days integer NULL, due_at timestamptz NULL, due_manual boolean NOT NULL DEFAULT false, done_at, done_by text, waived_reason text, notified_due_for date, created_by text, created_at, updated_at)`. `UNIQUE (event_id, template_item_id)` (Anwenden ist idempotent). CHECK: `done_at IS NULL OR waived_reason IS NULL`; `waived_reason IS NULL OR btrim(waived_reason) <> ''`. `position` ist Lexorank (Kopie `U todos/lexorank.py`). Indizes `(event_id, phase)` und `(assignee_sub) WHERE done_at IS NULL AND waived_reason IS NULL`. `events_app` bekommt `DELETE` (Arbeitsdaten, nicht in der E27-Liste); Löschen nur für Punkte ohne `template_item_id` (5.4).
- **Fälligkeit (Regel):** `due_at` = Ortsdatum von `starts_at` in `event.tzid` plus `due_offset_days` Tage, um 09:00 Ortszeit (`zoneinfo`, 09:00 ist nie mehrdeutig); ohne `starts_at` oder ohne Offset `NULL`. Neu berechnet werden nur Punkte mit `due_manual = false AND done_at IS NULL AND waived_reason IS NULL AND due_offset_days IS NOT NULL`; ein von Hand gesetztes `due_at` setzt `due_manual = true` und schützt den Punkt. Auslöser: **jede** Schreibstelle, die `starts_at` ändert (`events/writer.update_event`, `postpone` mit Termin, `revert_revision`, wirksam werdender Entwurf); sie ruft `checklist.recompute_due(session, event)` in derselben Transaktion. Die Antwort des Schreibweges trägt `checklistRecomputed: <n>` (Zahl der Punkte, deren `due_at` sich geändert hat; Hinweis "6 Fälligkeiten neu berechnet").
- **Seeds** (`backend/seeds/checklists.yaml`, idempotent über `slug`/`key` wie die M2-Taxonomie-Seeds, auch im Test-Harness). Inhalt ist **Startvorschlag, Luis prüft ihn (10.2 D4)**: PLAN 7.3 belegt nur die drei Offsets "Plakat bestellen −28", "Technik bestätigen −7", "Abrechnung +7".

| Vorlage | Punkte (`phase`, `required`, Offset) |
|---|---|
| `generic` | Raum bestätigt (planning, ja, −35) · Plakat bestellen (planning, nein, −28) · Technik bestätigen (live, ja, −7) · Helfer:innen informiert (live, nein, −3) · Abrechnung (followup, ja, +7) · Danke an Helfer:innen (followup, nein, +3) |
| `party` | wie `generic` plus Sicherheitskonzept liegt vor (planning, ja, −28) · Jugendschutz und Altersgrenze geklärt (planning, ja, −28) · Security und Sanitätsdienst bestätigt (live, ja, −7) |
| `meeting` | Einladung mit Tagesordnung (planning, nein, −7) · Protokoll verteilt (followup, ja, +7) |
| `trip` | Anmeldung geöffnet (planning, ja, −42) · Haftungsausschluss und Packliste (planning, ja, −28) · Teilnehmerliste final (live, ja, −3) · Abrechnung (followup, ja, +7) |

### 2.5 `quote` (neu, Vergleichsangebot)

`id uuid pk`, `event_id` (FK `RESTRICT`), `grp text` (1 bis 60, getrimmt, Beispiele Technik, Catering, Security), `vendor text` (1 bis 120), `amount_cents bigint CHECK >= 0`, `currency text NOT NULL DEFAULT 'EUR'` (CHECK `~ '^[A-Z]{3}$'`), `valid_until date`, `selected boolean NOT NULL DEFAULT false`, `note text` (<= 500), `attachment_id uuid` (FK `attachment.id` `RESTRICT`; die Datei muss `kind = quote` desselben Dossiers sein, Service), `created_by`, `created_at`, `updated_at`, `retired_at`. Partieller Unique-Index `uq_quote_selected` auf `(event_id, grp) WHERE selected AND retired_at IS NULL` (genau ein gewähltes Angebot je Gruppe). Kein `DELETE` (Ausblenden über `retired_at`). Die Tabelle statt `attachment.meta` (PLAN 7.6) trägt typisierte Beträge und den Unique-Index (Abweichung 10.1.2).

### 2.6 `notification`, `notification_pref` (neu)

- `notification(id uuid pk, recipient_sub text NOT NULL, kind text CHECK (7 Kinds, 5.7), event_id uuid FK NULL, params jsonb NOT NULL DEFAULT '{}', link text NOT NULL CHECK (link ~ '^/[^/\\]'), dedupe_key text UNIQUE NULL, created_at, read_at)`. Index `(recipient_sub, created_at DESC)` und partiell `(recipient_sub) WHERE read_at IS NULL`. `params` enthält nur Anzeigewerte (Titel des Dossiers, Name der handelnden Person, Zähler), keinen Freitext aus Kommentaren. Gelesene Zeilen älter als 90 Tage räumt der Worker (`events_app` bekommt `DELETE`).
- `notification_pref(principal_sub text, kind text, in_app boolean NOT NULL DEFAULT true, mail boolean NOT NULL DEFAULT true, updated_at, PRIMARY KEY (principal_sub, kind))`. Fehlt eine Zeile, gilt der Standard (alles an).

### 2.7 `media_ref` und `markdown_image` (Änderung)

`media_ref(image_id uuid FK markdown_image ON DELETE CASCADE, owner_type CHECK event|document|draft, owner_id uuid, PRIMARY KEY (image_id, owner_type, owner_id))`. `markdown_image.gc_marked_at timestamptz`. `events_app` bekommt `DELETE` auf `markdown_image` und `media_ref` (Zeilen in `deploy/db/roles.sql`, Stufe 2). **Datenschritt (Pflicht):** Rückfüllung aus `event.description_md` und aus `event_revision.snapshot ->> 'description_md'` (Regex auf `/api/media/images/<uuid>`), sonst löscht der erste GC-Lauf Bilder, die M3-Texte schon verwenden.

### 2.8 Rechte, View, Trigger

Die View `public_event_v` ändert sich nicht (kein Anhang außer Poster-Derivaten erreicht den Feed; Test `test_public_view_columns`). `attachment_poster_ok` bleibt wie 0004. Neue Append-only-Trigger: `document_revision`, `comment` (nur Auflösen erlaubt). `test_db_grants` wächst um: kein `DELETE` auf `attachment`, `document`, `document_revision`, `comment`, `quote`.

## 3. Upload-Regeln (Anhänge)

Ein Service `files/attachments.py` (Poster-Pfad aus `dossier/posters.py` ruft ihn mit `kind = poster` auf; die Route `POST /api/events/{id}/poster` bleibt als Alias, M1 bleibt gültig).

### 3.1 Typen und Größen

| Art | Erlaubt (nach Sniff, nie nach Client-Typ) | Limit |
|---|---|---|
| Bild (`poster`, `social_post`; auch in `other`, `howto_file`) | `image/png`, `image/jpeg`, `image/webp` | 10 MiB |
| Dokument (`business_plan`, `quote`, `contract`, `howto_file`, `other`) | `application/pdf`; `.docx`, `.xlsx`, `.pptx` (OOXML, auch als `application/zip` gesniffed, Container geprüft); `.odt`; `.md`, `.txt`, `.csv` (gesniffed `text/*`, Endung muss passen, strikt UTF-8, kein NUL) | 25 MiB |

`files/mime.py` bekommt `ATTACHMENT_MIMES`/`ATTACHMENT_EXTENSIONS` (engere Menge als die Workflow-Allowlist; die Workflow-Allowlist bleibt für andere Pfade). **Immer 415** `unsupported_media_type`: SVG (`image/svg+xml`, `text/xml`, `text/html`), GIF, `.doc/.xls/.ppt` (OLE2, Makros möglich), Makro-Formate (`.docm .xlsm .pptm .dotm`, und ein `.docx`/`.xlsx`/`.pptx`, dessen Container `vbaProject.bin` oder einen `macroEnabled`-Inhaltstyp enthält), ausführbare und Archivformate, Endung passt nicht zum Inhalt (`evil.exe` als `foto.png`). Bild in Dokument-`kind` und Dokument in Bild-`kind` (`poster`, `social_post`) ergibt 415. Zu groß: **413** `file_too_large` mit `limitBytes`; gelesen wird gedeckelt in Stücken (`_read_capped`), nie die ganze Datei vorher. nginx: Location `/api/events/` mit `client_max_body_size 26m` (E27, "+1 MiB"), alle anderen Locations unverändert.

### 3.2 Pipeline des Uploads

1. Berechtigung (`dossier.attach`, Zustandsregel aus `authorize_upload`, erweitert in 3.6), Dossier lesbar (sonst 404).
2. Lesen mit Deckel, Sniff, Erlaubnis nach 3.1, Größe nach Art.
3. Bild: `clean_image(data, POSTER_MIMES)` (Neukodierung, Pillow-Bombenschutz 40 MP, `Image.MAX_IMAGE_PIXELS`-Warnung als Fehler, EXIF/GPS fällt weg, 3.5). Fehler: `ImageRejected` ergibt 422 `image_rejected` mit Grund (`too_many_pixels`, `decode_failed`, `format_mismatch`); Poster unter 1200 px an der langen Kante ergibt 422 `image_too_small` (I08-Text). **Das Original wird nie gespeichert**, nur die neu kodierten Bytes.
4. Dokument: OOXML/ODT-Container wird als ZIP geprüft (höchstens 5000 Einträge, entpackt höchstens 200 MiB und Verhältnis höchstens 100:1, sonst 415 `archive_bomb`); PDF mit aktiven Namen (`/JavaScript`, `/JS`, `/Launch`, `/EmbeddedFile`, `/AA`, `/SubmitForm`, `/ImportData`, `/GoToR`, `/GoToE`, `/RichMedia`, `/OpenAction` ohne Seitenziel-Array) ergibt 415 `active_content`; gesucht wird nach Auflösen der `#xx`-Namensescapes, auch in entpackten Flate-Streams. Das ist eine Heuristik und kein Schutz, ClamAV bleibt das eigentliche Netz.
5. Speichern im privaten Bucket unter dem M1-Schlüsselschema; Zeile mit `scan_status = pending`; Eintrag im Audit (nur IDs). Commit, danach Scan-Job `scan:<id>` (Idempotenz wie M1).
6. Name: `display_name = sanitize_display_name` (NFC, `€`, Emoji und Umlaute bleiben), `storage_name = sanitize_storage_name` (ASCII). Download-Header ausschließlich über `content_disposition(display_name)`; ein Namen mit `€` oder Emoji darf nie 500 erzeugen (Regressionstest in Abnahme 9.3).

### 3.3 Scan und Quarantäne

`pending` und `error` bedeuten **Quarantäne**: Download und Vorschau antworten **409 `quarantined`**; `infected` (Objekt gelöscht, `storage_key` NULL) antwortet **410 `attachment_infected`**; beide Texte laut I08. Die Liste zeigt den Status als Text ("Wird geprüft", "Sauber", "In Quarantäne", "Infiziert"). `error` kann über `POST /api/attachments/{id}/rescan` (Recht `event.approve` in der Organisation oder `event.image_exception`-Inhaber, also `approver`/`editor`) neu eingereiht werden. Ohne `CLAMAV_HOST` bleibt jede Datei `pending` (M1, `settings.py:230`): keine stille Freigabe.

### 3.4 Vorschau und Derivate

Nach sauberem Scan baut der Worker für **jedes** Bild `preview_key` (WebP, lange Kante 400 px, privater Bucket, kein EXIF). Zusätzlich baut `derive_poster` (M1) die öffentlichen Derivate **nur für Poster** und nur im Public-Bucket. `GET /api/attachments/{id}/preview` liefert die private Vorschau (nach Lesecheck 5.1, `Cache-Control: private, max-age=300`); die öffentlichen Derivate bleiben dem Feed vorbehalten. Dokumente haben kein Vorschaubild (Dateisymbol).

### 3.5 Metadaten und EXIF-GPS (PLAN 18, Minor 4)

Bilder: Neukodierung entfernt EXIF/GPS in der gespeicherten Datei; ein Test lädt ein JPEG mit GPS-IFD hoch und prüft, dass weder die gespeicherten Bytes noch Vorschau oder Derivate ein EXIF-Segment tragen, auch nicht bei `shared`. Damit ist Minor 4 erledigt (Download-Original ohne GPS). **Dokumente** (PDF, OOXML, ODT) werden nicht bereinigt und können Autor:in, Programmversion oder eingebettete Fotos mit GPS enthalten (10.1.16); Gegenmaßnahme in M4: Hinweis im Upload-Dialog bei `shared` und keine Standardfreigabe außer `howto_file`.

### 3.6 Ersetzen und Ausblenden

- **Ersetzen** (`POST /api/attachments/{id}/replace`, multipart wie Upload, `kind` bleibt, Metadaten werden übernommen, sofern nicht neu mitgesendet): neue Zeile mit `supersedes_id = id`. Die alte Zeile wird erst ausgeblendet (`retired_at`), wenn die neue ersetzt hat.
- **Poster in `idea`/`planning`/`in_review`:** `hero_attachment_id` zeigt sofort auf die neue Zeile (M1-Verhalten, `image_required` wartet auf Scan und Derivate), die alte bekommt `retired_at` in derselben Transaktion.
- **Poster in `approved`/`live`** (löst M3 12.6; Recht: `approver` bzw. in `live` `event.edit_critical_live`, in beiden Fällen `editor`): `hero_attachment_id` bleibt auf der alten Datei. Der Worker-Job `promote_poster` (nach Scan und Derivaten, Schlüssel `promote:<id>`) tauscht in **einer** Transaktion `hero_attachment_id`, setzt `retired_at` der alten Datei, schreibt eine Revision (`field_class = critical`, Notiz "Poster ersetzt"), erhöht `public_seq` bei `live` und baut den Feed-Cache. Wird die neue Datei `infected`, bleibt die alte unberührt; der Anhang zeigt "In Quarantäne" und die Poster-Karte "Ersatz wartet".
- **Ausblenden** (`POST /api/attachments/{id}/retire`): setzt `retired_at`; das aktuelle Poster eines `approved`/`live`-Dossiers lässt sich nicht ausblenden (409 `poster_in_use`, Trigger-Fehler wird abgefangen). Es gibt kein Löschen (E27). Ausgeblendete und ersetzte Fassungen erscheinen nur mit `includeRetired=true`.
- Zustandsregel für Upload, Ersetzen, Metadaten: `idea`, `planning`, `in_review` (außer Poster: wie `authorize_upload` aus M3), `approved`, `live`, `followup` erlaubt für Nicht-Poster-Arten; `archived` und `withdrawn` sind schreibgeschützt (409 `dossier_closed`).

### 3.7 Rechte, Sichtbarkeit und Download

`attachment_readable(principal, event, attachment)` ist **eine reine Funktion** (Wahrheitstabelle als Test) nach PLAN 5.4:

| `visibility` | liest |
|---|---|
| `team` | `organizer`, `approver` der Organisation (Recht `event.submit` dort), `editor` (`dossier.read_restricted`) |
| `org` | jede Rolle mit Leserecht auf das Dossier in der Organisation, `stupa` (`event.read_all`), `editor` |
| `shared` | wie `org`; zusätzlich andere Organisationen und `member` **für archivierte Dossiers**, in M4 nicht erreichbar, weil `load_visible` fremde Dossiers weiter mit 404 verbirgt (10.1.8) |

Zusatzregel `quote/business_plan/contract` ("eingeschränkte Arten"): unabhängig von `visibility` nur mit `event.edit` in der Organisation oder `event.read_all`/`dossier.read_restricted` (`submitter` aufwärts, `stupa`, `editor`, `admin` über den Bypass); `viewer` und `member` sehen weder die Datei noch eine Zeile in der Liste noch einen Zähler. Die Liste filtert in SQL, nie nachträglich im Client. Ändern von `visibility` braucht `dossier.attach`; `shared` für eingeschränkte Arten ergibt 422 `visibility_not_allowed` ("Vergleichsangebote können nicht für alle Mitglieder freigegeben werden."), der CHECK ist das Netz. Download: `GET /api/attachments/{id}/download` streamt mit `Content-Disposition: attachment`, `Content-Type` aus dem gespeicherten Sniff, `X-Content-Type-Options: nosniff`, `Cache-Control: private, no-store`; nur Bilder dürfen über `preview` inline. Jeder Zugriff auf ein fremdes oder unlesbares Objekt antwortet 404 (nie 403).

## 4. Guards echt (Daten statt Platzhalter)

Die Guard-Funktionen und Codes aus M3 2.3 bleiben, ebenso die Zuordnung zu den Übergängen. M4 liefert die Daten im `Snapshot` (gebaut in `events/card_extras.py`, drei gruppierte Abfragen je Seite plus je Dossier eine Abfrage für `guard_snapshot`; `test_card_guards.py` wächst). Platzhalter-Standardwerte bleiben für Unit-Tests von `snap(...)`; **jeder Produktionsweg liefert echte Werte** (Test `test_snapshot_builders_set_m4_fields`).

| Guard (Code) | Übergang | Datenquelle und Regel |
|---|---|---|
| `openCommentRequired` (`open_comment_required`) | T03 | `Snapshot.open_comments` = Anzahl **offener Wurzelkommentare** des Dossiers (`resolved_at IS NULL AND parent_id IS NULL`). `None` gibt es in Produktion nicht mehr; der Guard blockt bei `0` (Test mit `None` bleibt als Verhalten der Unit-Fixtur) |
| `noOpenCommentOnField(hero)` (`open_comment_on_hero`) | T04 | `open_hero_comments` = offene Wurzelkommentare mit `anchor.field = 'hero'` oder `anchor.attachmentId` in der **Ersetzungskette** des aktuellen Posters (rekursiv über `supersedes_id` in beide Richtungen bis zur Wurzel); ein Austausch des Posters löst die Rückfrage nicht |
| `checklistDone(planning)` (`checklist_open`) | T02 | `open_required_checklist` = Punkte mit `phase = 'planning' AND required AND done_at IS NULL AND waived_reason IS NULL`. Die Abfrage nimmt die Phase als Parameter; T09 mit `followup` verdrahtet M5 |
| `attachmentsScanned` (`attachment_quarantined`) | wie M3 2.3 | `quarantined_attachments` = nicht ausgeblendete Anhänge mit `kind IN (poster, social_post)` oder `visibility = 'shared'` und `scan_status IN (pending, error)`; `infected` zählt nicht (Objekt weg) und blockt nicht, wird aber in der Liste sichtbar |
| `rightsComplete` (`rights_incomplete`) | wie M3 2.3 | siehe 4.3 |
| `flyerDateConfirmed` (`flyer_date`) | wie M3 2.3 | siehe 4.5 |

### 4.1 Auswirkung auf T03

T03 ("Änderungen anfragen") verlangt mindestens einen offenen Wurzelkommentar; das UI zwingt dazu, ihn im Dialog zu schreiben (4.2). `changes_requested` (5.7) nennt die Zahl der offenen Kommentare.

### 4.2 Kommentar im Übergangsdialog (I13)

Der T03-Dialog (M3 I13) bekommt ein Textfeld "Rückfrage". Es legt vor dem Übergang einen Kommentar an (`POST /comments`, Anker optional) und feuert dann T03; scheitert T03, bleibt der Kommentar bestehen (kein Rollback über Routen hinweg). Die Notiz des Übergangs (`note`) bleibt davon unabhängig.

### 4.3 `rights_complete` und `image_required`

`rights_complete` prüft für das aktuelle Poster (ohne Bildausnahme) **vier Felder** und meldet je fehlendem ein eigenes `rights_incomplete` mit `field ∈ altText | credit | rightsBasis | consentNote` und `fixAction = fill_rights`: `alt_text` nicht leer, `credit` nicht leer, `rights_basis <> 'unknown'`, bei `persons_depicted` ein nicht leerer `consent_note`. `image_required` prüft **nur noch** Existenz, `scan_status = clean` und Derivate (`PosterSnapshot.usable_media`); `PosterSnapshot.usable` (alle Teile) bleibt als Spiegel der SQL-Funktion `attachment_poster_ok` und des Triggers (das harte Netz bleibt unverändert). Folge: ein sauberes Poster ohne Alt-Text meldet `rights_incomplete/altText` statt `image_required` (Abweichung 10.1.7; betroffene M3-Tests werden angepasst).

### 4.4 Social-Post und Rechte

Für `social_post` gilt dieselbe Rechteprüfung beim Setzen von `meta.status = planned` (422 `rights_incomplete` mit Feldliste); sie ist kein Übergangs-Guard.

### 4.5 Flyer-Check

`PosterSnapshot.reused_in_other_year` = `true`, wenn (a) die `sha256` des Posters an einem anderen Dossier mit anderem Startjahr hängt, das nicht zur selben Serie gehört (Serien kommen mit M7; bis dahin zählt jedes andere Dossier), oder (b) `contains_date` gesetzt ist und das Jahr von `dated_for` vom Startjahr des Dossiers abweicht. Bestätigt gilt der Flyer, wenn `event.flyer_checked_at >= poster.created_at` (Guard unverändert). Die Aktion `confirm-flyer` setzt zusätzlich `attachment.flyer_date_confirmed_at/_by` am Poster und schreibt wie in M3 eine Revision (`field_class = dossier`). Ein Ersetzen des Posters setzt die Bestätigung zurück (neues `created_at`).

## 5. API-Vertrag M4

Alle Pfade unter `/api`, JSON in camelCase, `extra=forbid`, Fehler als Problem+JSON mit `code` und `reasons[]`, Zeiten tz-aware ISO-8601. RBAC ausschließlich über `Principal.has(perm, org_id)` im Service (Entscheidung nach dem Laden, 404-Regel: unlesbares Dossier oder Objekt eines unlesbaren Dossiers ergibt 404). Jede Route steht in `ROUTE_PERMS` (CI bricht sonst, M2 Abschnitt 7). Listen nutzen `shared/paging.py`.

### 5.1 Anhänge (Besitzer `backend-dossier`)

| Methode, Pfad | Recht | Beschreibung |
|---|---|---|
| `GET /events/{id}/attachments?kind=&includeRetired=` | Lesen des Dossiers; gefiltert nach 3.7 | `AttachmentOut[]` gruppiert nach `kind`, je Eintrag `id, kind, displayName, mime, sizeBytes, visibility, scanStatus, altText, credit, rightsBasis, licenseRef, sourceUrl, personsDepicted, consentNote, containsDate, datedFor, meta, supersedesId, retiredAt, createdAt, hasPreview, replacedBy` |
| `POST /events/{id}/attachments` | `dossier.attach` | multipart: `file`, `kind`, optional `visibility`, `altText`, `credit`, `rightsBasis`, `licenseRef`, `sourceUrl`, `personsDepicted`, `consentNote`, `containsDate`, `datedFor`, `meta` (JSON-Text). 201 `AttachmentOut`. Fehler: 413, 415, 422 (`image_rejected`, `image_too_small`, `consent_missing`, `visibility_not_allowed`), 409 `field_locked`/`dossier_closed` |
| `PATCH /attachments/{id}` | `dossier.attach` | `visibility`, `displayName`, Rechtefelder, `meta`; `personsDepicted: true` ohne `consentNote` ergibt 422 `consent_missing`. Ohne ETag, letzter Schreiber gewinnt (10.1.6); Audit-Eintrag |
| `POST /attachments/{id}/replace` | wie 3.6 | multipart wie Upload; 201 neue Zeile |
| `POST /attachments/{id}/retire` | `dossier.attach` | 204; 409 `poster_in_use` |
| `POST /attachments/{id}/rescan` | `approver`/`editor` | 202; nur bei `scan_status = error` |
| `GET /attachments/{id}/download` | 3.7 | Stream; 409 `quarantined`, 410 `attachment_infected` |
| `GET /attachments/{id}/preview` | 3.7 | WebP-Stream; 404 ohne Vorschau |
| `GET /events/{id}/dossier-counts` | Lesen | `{attachments, quotes, howto, openChecklist, mailTemplates, openComments}` für die Tab-Zähler (eingeschränkte Zähler nur mit Recht, sonst weggelassen) |

`POST /events/{id}/poster` bleibt (Alias, M1). `GET /events/{id}/poster` bleibt.

### 5.2 Dokumente (`backend-dossier`)

| Methode, Pfad | Recht | Beschreibung |
|---|---|---|
| `GET /events/{id}/documents?kind=` | Lesen, gefiltert nach `visibility` wie 3.7 | `DocumentOut[]` ohne Rumpf (`id, kind, title, visibility, carryOver, rev, verifiedAt, verifiedBy, updatedAt`) |
| `POST /events/{id}/documents` | `event.edit` | `{kind ∈ howto|notes, title, bodyMd?, visibility?, carryOver?}`; zweites `howto` ergibt 409 `already_exists`; legt Revision 1 an; 201 mit `ETag: "<rev>"` |
| `GET /documents/{id}` | Lesen | `DocumentOut` mit `bodyMd`, `meta`, ETag |
| `PUT /documents/{id}` | `event.edit` | `{title?, bodyMd, changeNote?, visibility?, carryOver?}` mit **Pflicht** `If-Match` (428 ohne, 409 `conflict` mit `current` bei Abweichung, `*` zählt nicht); schreibt eine neue `document_revision` und erhöht `rev`; identischer Rumpf und Titel ist ein No-op (200, gleicher ETag, keine Revision). Bilder im Rumpf pflegen `media_ref` (8). Autosave erzeugt **keine** Revision (unten) |
| `GET /documents/{id}/revisions` | Lesen | `[{rev, actorId, actorType, changeNote, at, titleChanged, charsDelta}]` absteigend |
| `GET /documents/{id}/revisions/{rev}` | Lesen | volle Revision; unbekannte oder fremde Revision 404 |
| `GET /documents/{id}/diff?from=&to=` | Lesen | serverseitiger Zeilen-Diff (`difflib.SequenceMatcher` über `splitlines()`), Antwort `{from, to, lines: [{op: "equal"|"add"|"remove", text, fromLine, toLine}], added, removed}`; Obergrenze 2000 Zeilen je Seite, sonst 422 `diff_too_large` |
| `PUT /documents/{id}/draft`, `GET`, `DELETE` | `event.edit` | Autosave in `editor_draft` (`owner_kind = document`), `If-Match` = `base_rev`, Rumpf <= 256 KiB (Streaming-Abbruch wie M3 12.26), kein Audit, keine Revision, schreibt `media_ref` mit `owner_type = draft`; Schreibregeln wie M3 4.3 |

`DELETE` eines Dokuments gibt es nicht. Schreiben ist in `archived` und `withdrawn` gesperrt (409 `dossier_closed`).

### 5.3 Checkliste (`backend-dossier`)

| Methode, Pfad | Recht | Beschreibung |
|---|---|---|
| `GET /events/{id}/checklist` | Lesen | `{items: ChecklistItemOut[], openRequired: {planning, review, live, followup}, template: {slug, name} | null}`; je Punkt `id, text, phase, required, position, assigneeSub, assigneeName, dueAt, dueOffsetDays, dueManual, overdue, doneAt, doneBy, waivedReason, fromTemplate` |
| `POST /events/{id}/checklist/apply-template` | `event.edit` | `{templateSlug?}`; Standard Auflösung 2.4; idempotent (`UNIQUE (event_id, template_item_id)`); 200 mit der Liste und `added: n` |
| `POST /events/{id}/checklist/items` | `event.edit` | `{text, phase, required?, assigneeSub?, dueAt?}`; `dueAt` setzt `dueManual` |
| `PATCH /checklist-items/{id}` | `event.edit` | `{text?, phase?, required?, assigneeSub?, dueAt?|null, waivedReason?, position?}`; `dueAt: null` hebt `dueManual` auf und rechnet neu; Vorlagenpunkte dürfen `text`/`phase` nicht ändern (409 `template_item`) |
| `POST /checklist-items/{id}/done` | `event.edit` **oder** zugewiesene Person | `{done: boolean}`; setzt `doneAt/doneBy` bzw. hebt auf; erledigt und entfallen schließen sich aus (409 `item_waived`) |
| `DELETE /checklist-items/{id}` | `event.edit` | nur Punkte ohne Vorlage (409 `template_item`); 204 |

Regeln: Entfallen setzt `waivedReason` (Pflichtpunkt: mindestens 10 Zeichen, sonst 422 `waiver_reason_required` "Pflichtpunkt kann nur mit Grund entfallen."; optionaler Punkt: nicht leer). `assigneeSub` muss Mitglied der Organisation oder `editor` sein, sonst 422 `assignee_not_member` ("Diese Person gehört nicht zur Organisation."). Eine neue Zuweisung an eine andere Person löst `task_assigned` aus (5.7). Schreiben in `archived`/`withdrawn` gesperrt. Das Frontend kennt `overdue` nur aus der Antwort (`dueAt < now AND offen`).

### 5.4 Meine Aufgaben (I02)

`GET /api/tasks` (M3) liefert zusätzlich Abschnitt `kind = checklist_item`: offene Punkte (`done_at IS NULL AND waived_reason IS NULL`) mit `assignee_sub = ich` in Dossiers, die ich lesen darf, sortiert nach `dueAt` (nulls zuletzt), mit `eventId`, `eventTitle`, `text`, `phase`, `dueAt`. Besitzer der Änderung ist `backend-dossier` (kleine Ausnahme im Modul `tasks`).

### 5.5 Kommentare (`backend-dossier`)

| Methode, Pfad | Recht | Beschreibung |
|---|---|---|
| `GET /events/{id}/comments?open=` | Lesen | Threads: Wurzeln mit `replies[]`, je Kommentar `id, authorSub, authorName, actorType, bodyMd, anchor, parentId, resolvedAt, resolvedBy, createdAt`; `open=true` nur offene Wurzeln |
| `POST /events/{id}/comments` | `comment.write` | `{bodyMd, anchor?, parentId?}`; Antworten tragen keinen Anker; Anker nach 2.3 validiert (fremdes Objekt oder falsche Offsets 422 `anchor_invalid`); 201; löst `comment_added` aus |
| `POST /comments/{id}/resolve` | Autor:in, `approver` der Organisation oder `editor` | nur Wurzeln (409 `not_a_root`); setzt `resolvedAt/By`; idempotent (200 beim zweiten Mal); löst `comment_resolved` an die Autorin aus, wenn jemand anderes auflöst |
| `POST /comments/{id}/reopen` | wie `resolve` | setzt die Auflösung zurück (Trigger erlaubt `resolved_*`) |

`comment.write` hat `stupa` global; `member`/`viewer` können lesen, wenn das Dossier lesbar ist, aber nicht schreiben. Kommentare erscheinen nicht in `event_revision`; die Zahl `openComments` steht in `EventOut.guardsSummary` nicht, nur in `dossier-counts` und den Guards.

### 5.6 Mailvorlagen (`backend-dossier`, Fassade über `document.kind = mail_template`)

| Methode, Pfad | Recht | Beschreibung |
|---|---|---|
| `GET /events/{id}/mail-templates` | Lesen | Liste (`id, title, subject, visibility, rev, updatedAt`) |
| `GET /events/{id}/mail-templates/{docId}` | Lesen | mit `bodyMd`, `meta`, ETag |
| `PUT /events/{id}/mail-templates/{docId}` | `event.edit` | wie `PUT /documents`, plus `{subject, toHint?}`; `docId = new` legt an; Validierung unten |
| `POST /events/{id}/mail-templates/{docId}/render-preview` | Lesen | `{subject?, bodyMd?}` (ungespeicherter Entwurf) oder leer (gespeicherter Stand); Antwort `{subject, body}` (Klartext) oder 422 mit `reasons[]` |
| `GET /mail-template-placeholders` | angemeldet | Katalog `[{path, label, example}]` |

**Platzhalter-Katalog v1** (PLAN 7.5): `event.title`, `event.starts_local`, `venue.name`, `org.name`. `event.starts_local` ist Datum und Uhrzeit in `event.tzid` (`dd.MM.yyyy, HH:mm Uhr`, de). Fehlt der Ort, ist `venue.name` die leere Zeichenkette, nie `None`. Erweiterungen (`event.ends_local`, `event.summary`, `org.short`, `venue.address`) sind Vorschlag D5.

**Validierung beim Speichern und beim Rendern:** Parsen in `SandboxedEnvironment` mit `StrictUndefined`; erlaubt sind **nur Ausdrücke** `{{ pfad }}` mit Pfaden aus dem Katalog; `{% … %}`-Anweisungen, Filter, Aufrufe, Indexzugriffe und Attribute außerhalb des Katalogs ergeben **422** `template_invalid` mit `reasons[]` je Fund (`code = unknown_placeholder` mit `field = event.raum` und `allowed[]`, oder `statement_not_allowed`, `syntax_error` mit Zeile). Der Betreff darf weder in der Quelle noch gerendert CR oder LF enthalten (422 `subject_newline`), Länge <= 200. Beim Rendern greift `StrictUndefined` als zweite Sicherung (`TemplateRenderError` wird 422, nie 500). Der Server **versendet nie** aus dem Dossier; Kopieren und `mailto:` baut das Frontend (7.5 PLAN, "kein Versand aus dem Dossier").

### 5.7 Benachrichtigungen (`backend-mail`)

**Kinds (Katalog `notifications/kinds.py`, ersetzt die drei M1-Kinds; es gibt keine Datenhalde, die migriert werden müsste):**

| Kind | Auslöser | Empfang | Kanal | abschaltbar |
|---|---|---|---|---|
| `review_requested` | T02 | Personen mit `event.approve` in der Organisation (Mitgliedschaft) und alle `editor` (Redaktion); bei Dossier ohne Organisation nur `editor` | In-App + Mail | ja |
| `changes_requested` | T03 | `created_by`, `submitted_by`, alle `organizer` der Organisation | In-App + Mail | **nein (essenziell)** |
| `comment_added` | neuer Kommentar oder Antwort | `created_by`, `submitted_by`, `organizer`/`approver` der Organisation, bisherige Kommentierende des Dossiers (keine Autorin selbst) | In-App + Mail | ja |
| `comment_resolved` | Auflösen durch eine andere Person | Autor:in der Wurzel | In-App | ja |
| `transition_done` | jeder Übergang und jede Aktion (`cancel`, `postpone`, `reinstate`) außer T02, T03 | `created_by`, `submitted_by`, `organizer` der Organisation, außer der handelnden Person und `system:`-Akteuren ohne Mensch | In-App | ja |
| `task_assigned` | Zuweisung eines Checklistenpunkts | zugewiesene Person (nicht bei Selbstzuweisung) | In-App + Mail | ja |
| `checklist_due` | Fälligkeit morgen (Ortsdatum Europe/Berlin) | zugewiesene Person | In-App + Mail | ja |

`changes_requested` ist PLAN 9.4 "nicht abschaltbar"; die übrigen PLAN-Kinds (`proposal_created`, `edited_after_publish`, `review_overdue`, `followup_reminder`, `event_cancelled`, `import_digest`, `source_failed`, Erwähnungen) gehören zu M5/M6/B (10.1.12). Tages-Digest ist Stufe B.

**Erzeugung:** `notifications/service.notify(session, kind, recipients, event, params, dedupe_key)` fügt In-App-Zeilen **in der Transaktion der Ursache** ein (respektiert `notification_pref.in_app`), sammelt die Mails, die nach dem Commit als Aktion mit Schlüssel `notif:<id>:mail` (Redis `SET NX`, wie `pipeline/actions.py`) in die Mailqueue gehen (respektiert `notification_pref.mail`). Die handelnde Person bekommt nie eine Benachrichtigung zu ihrer eigenen Handlung. `dedupe_key` verhindert Doppelzeilen (`checklist_due:<itemId>:<dueDate>`). Aufrufer in `pipeline/service` (Übergänge), `pipeline/actions_service`, `dossier/comments`, `dossier/checklist` rufen `notify` nach der fachlichen Änderung; die Signatur liefert `backend-mail` zuerst (Abschnitt 11).

**Mail:** Templates liegen unter `notifications/templates/de/<kind>.{subject,txt,html}.j2` (Jinja-Sandbox, `StrictUndefined`, `autoescape` für HTML, Betreff ohne CR/LF); nur Deutsch (`mail_default_lang = de`), Links absolut aus `public_base_url`. Der Idempotenzschlüssel ist der arq-`_job_id` (`compute_idempotency_key("notif", id)`). **Ohne erreichbares Redis wird die Mail verworfen** und mit Warnung geloggt (ohne Adresse); die In-App-Zeile und die fachliche Aktion bleiben davon unberührt (kein 500, kein Wiederholen aus der Anfrage). `DirectMailQueue` bleibt Unit-Tests vorbehalten; Produktion und Integration bauen `ArqMailQueue` oder `NullMailQueue` (verwirft). Der Capture-Mechanismus ist `CapturingMailSender` (kein SMTP; Produktivversand nur mit `smtp_host`).

**Fälligkeits-Cron** `worker/mail.py: send_due_reminders` (arq-Cron stündlich, Minute 10 UTC; arq rechnet in UTC, das Ortsdatum bestimmt der Job selbst): wählt offene Punkte mit zugewiesener Person, `due_at`-Ortsdatum = morgen (Europe/Berlin) und `notified_due_for` verschieden vom Fälligkeitsdatum, setzt `notified_due_for` und ruft `notify`. Idempotent; Änderung der Fälligkeit löst eine neue Mail aus.

**API:**

| Methode, Pfad | Recht | Beschreibung |
|---|---|---|
| `GET /notifications?unread=&limit=&cursor=` | angemeldet | eigene Einträge `{id, kind, eventId, eventTitle, params, link, createdAt, readAt}`, neueste zuerst, Standard 30 |
| `GET /notifications/unread-count` | angemeldet | `{count}` (billige Abfrage für die Glocke) |
| `POST /notifications/{id}/read` | angemeldet | 204; fremde oder unbekannte Id 404 |
| `POST /notifications/read-all` | angemeldet | 204 |
| `GET /account/notification-prefs` | angemeldet | `{items: [{kind, inApp, mail, essential}]}` für alle Kinds |
| `PUT /account/notification-prefs` | angemeldet | `{items: [{kind, inApp, mail}]}` (Teilmenge erlaubt); essenzielle Kinds mit `false` ergeben 422 `kind_essential`; unbekannte Kinds 422 |

Die Glocke fragt `unread-count` alle 60 s, solange der Tab sichtbar ist, und bei jedem Routenwechsel; kein Server-Push (Push ist B). Aufbewahrung: Worker `gc_notifications` löscht gelesene Zeilen nach 90 Tagen.

### 5.8 Vergleichsangebote (`backend-dossier`)

| Methode, Pfad | Recht | Beschreibung |
|---|---|---|
| `GET /events/{id}/quotes` | `event.edit` in der Organisation, `event.read_all`, `dossier.read_restricted` | `{groups: [{grp, quotes: QuoteOut[], cheapestId, selectedId}], selectedTotalCents, selectedTotalCurrency, suggestedBudgetCents}`; `QuoteOut` mit `expired` (`validUntil < heute`), ausgeblendete nur mit `includeRetired` |
| `POST /events/{id}/quotes` | `dossier.attach` | `{grp, vendor, amountCents, currency?, validUntil?, note?, attachmentId?}` |
| `PATCH /quotes/{id}` | `dossier.attach` | Teilfelder; `selected` nur über `select` |
| `POST /quotes/{id}/select` | `dossier.attach` | wählt, hebt die Wahl derselben Gruppe in einer Transaktion auf; abgelaufenes Angebot ergibt 409 `quote_expired` |
| `DELETE /quotes/{id}` | `dossier.attach` | blendet aus (`retired_at`), 204 |

Fremde Organisation: 404 (Dossier nicht lesbar). Gleiche Organisation ohne Recht (`viewer`, `member`): **403** `forbidden` ohne Beträge im Fehlerrumpf. Die Summe zählt nur gewählte Angebote derselben Währung (`EUR`); andere Währungen erscheinen mit Hinweis und bleiben außerhalb der Summe. `suggestedBudgetCents` ist ein Vorschlag, der Server setzt `facts.budget_cents` nie (PLAN 7.6). Beträge stehen nirgends sonst: nicht in `EventOut`, Karten, Revisionen, Feed, Benachrichtigungen, Audit (Test `test_quote_amounts_not_leaked`).

### 5.9 Problem+JSON: neue Codes

`file_too_large` 413 · `unsupported_media_type` 415 · `archive_bomb`, `active_content` 415 · `image_rejected`, `image_too_small`, `consent_missing`, `visibility_not_allowed`, `social_post_needs_image`, `anchor_invalid`, `template_invalid`, `subject_newline`, `diff_too_large`, `waiver_reason_required`, `assignee_not_member`, `kind_essential` 422 · `quarantined`, `poster_in_use`, `dossier_closed`, `already_exists`, `template_item`, `item_waived`, `not_a_root`, `quote_expired`, `conflict` 409 · `attachment_infected` 410 · `precondition_required` 428.

## 6. Frontend-Screens

Alle Screens folgen PLAN 15.1 Wort für Wort (Elemente, Zustände, Leer, Fehler, Komponenten); der Kontrakt hält nur die Verdrahtung fest. Standalone, OnPush, Signals, separate `.html`/`.scss`, Texte in `i18n/de` (gegendert, Doppelpunkt oder neutral), Kit-Tokens, Hell und Dunkel, Handy-Breite 360 px ohne horizontales Scrollen, axe grün.

### 6.1 Routen und Reiter

Kindrouten von `/dossiers/:id`: `` (Übersicht, I07), `anhaenge` (I08), `anleitung` (I09), `checkliste` (I10), `mails` (I11), `verlauf` (I12). `app-tabs` mit Zählern aus `GET /events/{id}/dossier-counts`; Tab "Verlauf" ersetzt den minimalen Verlauf aus M3. Die Reiter laden lazy. `/konto` (I27) und die Glocke (I28) sind schon Teil der Shell.

### 6.2 Neue Bausteine (Kopien mit PROVENANCE, Nachbauten mit "Pattern from")

- `shared/markdown/*` aus `U frontend/src/app/shared/markdown/*` (`markdown.util.ts` escape-first Renderer, `markdown-view`, `markdown-image-upload.directive`, `media-api.service`, `internal-link`, `linkify`): nur über `markdownToSafeHtml`; `bypassSecurityTrustHtml` ausschließlich in `markdown-view` (Contract-Spec bleibt).
- `shared/ui/history`, `shared/ui/chat` (Kommentar-Thread) aus U; `shared/ui/markdown-diff` (`app-markdown-diff`, **Nachbau**, rendert die Antwort von `GET /documents/{id}/diff`: Zeilen mit Plus/Minus, Zeilennummern, nur Text, Wortumbruch, Farbe plus Zeichen, nie Farbe allein); `shared/ui/quote-table` (`app-quote-table`, Nachbau auf Kit-`app-data-table`; Karten unter 768 px).
- Tiptap: Pfad-Alias `@stupa-makers/ui-kit/markdown-editor` in `tsconfig.json` und `jest.config.js`, Verwendung ausschließlich per dynamischem `import()` (kein Eintrag im Initial-Bundle; `npm run build` prüft die Budget-Größe).
- `features/dossiers/editor/dossier-markdown-editor`: Hülle um `app-markdown-editor` mit Umschalter **Editor | Quelltext** (`app-segmented`), Textarea mit `appMarkdownImageUpload` und Vorschau im Quelltextmodus, Bilder-Upload sequentiell (429), Autosave alle 15 s gegen `PUT .../draft` (nur bei Änderung, Wiederholung nur bei Netz-/5xx-Fehlern, M3 12.26), `CanDeactivate`, Konfliktansicht (409) wie M3, Fehlertext "Speichern fehlgeschlagen, dein Text bleibt lokal erhalten." (localStorage-Kopie des Entwurfs, in try/catch). Dieselbe Hülle bedient `description_md` in I07 (E20 nennt Beschreibung), die Anleitung und die Mailvorlage.

### 6.3 I08 Anhänge (`anhaenge`)

Gruppen Poster · Social-Posts · Unterlagen (Businessplan, Verträge) · Vergleichsangebote · Sonstiges. Unterlagen und Vergleichsangebote erscheinen nur, wenn die API sie liefert (3.7), nie als leere Gruppe mit Hinweis auf Beträge. Upload über `app-file-drop-zone` (Tastaturpfad "Datei wählen") und `app-poster-upload` mit allen Pflichtfeldern (Alt-Text, Credit, Rechtegrundlage, "Personen erkennbar" mit Pflichtfeld Einwilligung, "Datum im Bild" mit Datum, Hinweis zum Vorjahres-Flyer). Fehlertexte aus I08, mit Dateigröße in MB und Limit aus `limitBytes`. Scan-Status als Text, nie nur Farbe. Menü: Ersetzen, Ausblenden, Herunterladen, Sichtbarkeit (Team, Organisation, Alle Mitglieder; Option "Alle Mitglieder" für eingeschränkte Arten ausgeblendet). Ersetzte Fassungen einklappbar ("2 ältere Fassungen"). Poster mit offener Rückfrage trägt die Marke "Rückfrage offen". `app-quote-table` je Gruppe mit `app-currency-input`, Spalten Anbieter, Betrag, gültig bis, gewählt; günstigstes Angebot markiert (Text "günstigstes"), abgelaufenes `validUntil` als Fehlertext, Summe der Wahl mit Knopf "Als Budget übernehmen" (setzt nur das Formularfeld `facts.budgetCents`, speichert nicht). Social-Post-Formular (Kanal, Konto, Caption, geplant für, Status; "planned" nur mit Bild).

### 6.4 I09 Anleitung (`anleitung`), I11 Mails (`mails`)

I09: eine Spalte "Diese Ausgabe" (Master-Spalte mit M5), `dossier-markdown-editor`, Knopf "Als neue Fassung speichern" öffnet Dialog mit Änderungsnotiz (`PUT` mit `If-Match`), Kopf "Zuletzt geprüft von … am …" oder (ab M5) Warnung; Hinweis "Bitte keine privaten Telefonnummern oder Adressen. Nutzt Funktionsadressen."; Leerzustand mit "Vorlage einfügen" (fester Gerüsttext, Bibliotheksvorschläge sind M5). I11: `app-list-detail` mit Vorlagenliste, Detail mit Betreff, Editor, Platzhalterliste (Klick fügt `{{ pfad }}` ein), Live-Vorschau (debounced `render-preview`, Fehler als `app-note` mit "Unbekannter Platzhalter {{ event.raum }}. Erlaubt sind: …"), Knöpfe "Text kopieren" (Clipboard, Fallback Markierung), "Als Mail öffnen" (`mailto:` mit `encodeURIComponent`, ab 1800 Zeichen Hinweis "Text zu lang für den Mailknopf, bitte kopieren"), "Als Vorlage für das Format speichern" nur sichtbar, wenn M5 das Format liefert (in M4 ausgeblendet).

### 6.5 I10 Checkliste (`checkliste`)

Gruppen je Phase (Planung, Freigabe, Veranstaltung, Nachbereitung), Punkt mit `app-checkbox`, Pflichtkennzeichen als Text "Pflicht", Zuständige Person (`app-select` aus Mitgliedern der Organisation), Fälligkeit als `due-chip` (relativ "4 Wochen vorher" und absolut, überfällig in Fehlerfarbe plus Text "überfällig"), Menü "entfällt mit Grund", "Zuweisen", "Löschen" (nur ohne Vorlage), "Punkt hinzufügen", "Vorlage anwenden". Nach Datumsänderung im Formular zeigt die Übersicht den Hinweis "n Fälligkeiten neu berechnet" aus `checklistRecomputed`. Fehlertexte aus I10. T02-Guard `checklist_open` verlinkt mit dem Knopf "Checkliste" auf diesen Reiter (`FixAction.OPEN_CHECKLIST`).

### 6.6 I12 Verlauf und Kommentare (`verlauf`)

Zeitleiste (`app-history`): Revisionen (Feldklasse, Notiz), Übergänge, Aktionen, Dokumentrevisionen; Diff zweier Revisionen: Felder über `app-config-diff`, Texte über `app-markdown-diff`; "Auf diesen Stand zurücksetzen" nur für Prüfende (`revert-revision`, M3). Kommentar-Threads (`app-chat`) mit Anker-Chip ("am Poster", "am Titel", "an Anhang xy.pdf", "in der Anleitung"), Knopf "Erledigt" (und "Wieder öffnen"), Eingabe auf dem Handy als Sheet. **Anker am Objekt:** neben jedem verankerbaren Feld (`hero`, Titel, Kurztext, Beschreibung, Termin, Ort) und je Anhang ein Knopf "Rückfrage" mit Popover-Eingabe (`POST /comments` mit Anker); Felder und Anhänge mit offener Rückfrage tragen die Marke "Rückfrage offen" (Text plus Symbol) und springen beim Klick zum Thread. Im Anleitungs-Editor ermöglicht Textauswahl im Quelltextmodus eine Rückfrage mit `{documentId, rev, from, to}`. Leer: "Noch kein Verlauf." / "Noch keine Rückfragen."

### 6.7 I27 Konto, I28 Inbox

I27 (`/konto`): neuer Abschnitt "Benachrichtigungen" (`app-field-group`, je Kind zwei `app-switch` "In der App" und "Per Mail"; essenzielle Kinds gesperrt mit Hinweis "Immer aktiv"); Speichern sofort je Schalter (`PUT`, Rückfall bei Fehler). I28: Glocke in der Nav-Rail und der Bottom-Bar mit `app-badge`-Zähler (99+ gedeckelt, Zähler auch als `aria-label`), `app-side-sheet` mit Liste (Art als Text, Dossier, relative Zeit, ungelesen mit Punkt **und** Fettschrift), Klick markiert gelesen und navigiert zu `link`, "Alle gelesen"; leer: "Keine neuen Benachrichtigungen." Laden bei Öffnen, Zähler wie 5.7.

### 6.8 i18n, API-Client, Typen, Dateien

Typen in `features/dossiers/model/` spiegeln 5.x (camelCase); der API-Client wirft keine Typen weg (`extra=forbid` auf dem Server verlangt exakt passende Bodies). Neue Dateien: `features/dossiers/{attachments,howto,checklist,mails,activity,editor}/`, `features/notifications/{bell,inbox}/`, `features/account/notification-prefs/`, `shared/markdown/*`, `shared/ui/{history,chat,markdown-diff,quote-table}/`. Je Datei Kopf-Docstring, kleine Dateien, keine Trennkommentare.

## 7. Roundtrip-Gate E20

**Korpus:** `frontend/tests/fixtures/markdown/*.md`, **30 Dateien** (E20), nie unter 15 (Auftragsfloor): mindestens je zwei zu geordneten und ungeordneten Listen (verschachtelt bis Tiefe 3), Aufgabenlisten, Tabellen (mit Ausrichtung), Links (inline, Referenz, Autolink), Bilder auf `/api/media/images/<uuid>`, Code (Inline, eingezäunt mit Sprache), Zitate, Überschriften 1 bis 4, Hervorhebung (`*`, `**`, `~~`), harte und weiche Umbrüche, Umlaute, `ß`, `€`, Emoji (inkl. ZWJ-Folgen), Mailvorlagen mit `{{ event.title }}`, leere Zeilen am Dateiende (mit und ohne Zeilenumbruch), CRLF-Datei. Jede Datei ist eine reale Anleitung oder Mailvorlage aus dem Movienight-/Party-/Ausfahrt-Material (PLAN 7.3) oder ein gezielter Randfall; ein Kopf-Kommentar ist nicht erlaubt (Byte-Gleichheit).

**Test (`roundtrip.gate.spec.ts`, Jest/jsdom):** je Datei `exportMarkdown(importMarkdown(text)) === text` über **denselben Import-/Export-Pfad wie `app-markdown-editor`** (Kit-Public-API, keine Nachbildung), Vergleich auf Byte-Ebene (`Buffer.compare`). Kein Normalisieren, keine Ausnahmeliste.

**Entscheidung (dokumentiert, mechanisch):** Ein Skript `npm run gate:roundtrip -- --write` führt den Test aus und schreibt `frontend/src/app/shared/markdown/roundtrip-gate.json` `{passed, failed[], corpusHash, kitCommit}`. Ein Test schlägt fehl, wenn `corpusHash` oder `kitCommit` nicht zum Stand passen. **Ist `passed = true`, ist Tiptap der Standardmodus, sonst ist die Textarea (Quelltext) der Standard und Tiptap per Umschalter optional** (E20, PLAN-Zeile M4). Die Abnahme trägt das Ergebnis und die Liste `failed` ein. Zusätzlich gilt **je Dokument zur Laufzeit**: bevor ein vorhandener Text im Editor-Modus öffnet, rechnet der Client denselben Roundtrip auf genau diesem Text; weicht er ab, öffnet der Text im Quelltextmodus mit Hinweis "Dieser Text wird im Editor nicht verlustfrei dargestellt. Bearbeite ihn als Quelltext." Gespeichert wird immer Markdown, nie HTML. Backend-Gegenprobe: `test_document_body_stored_verbatim` speichert alle Korpusdateien über `PUT` und liest sie byte-gleich zurück (die API normalisiert nicht).

## 8. Media-Router und GC-Worker

**Router (Kopie `U media/router.py`, M1-Lücke H4):** `POST /api/media/images` (Recht `comment.write` oder `event.edit`, angemeldet reicht nicht; Rate-Limit wie Upstream, sequentiell vom Client), Antwort `MarkdownImageOut`; `GET /api/media/images/{id}` streamt (`Cache-Control: private, max-age=3600`, `nosniff`), die uuid4 ist die Berechtigung (Upstream-Modell: kein Uploader-Bezug, kein Personenbezug); Eintrag in `ROUTE_PERMS`.

**`media_ref` pflegen:** `documents.put` und `events.writer` (bei `description_md`) schreiben beim Speichern alle in `image_ids_in(body)` gefundenen Ids als `(image, owner_type, owner_id)`; **es wird nie entfernt**, solange der Besitzer lebt (Revisionen sind append-only und brauchen ihre Bilder für Zurücksetzen und Diff). Der Autosave ersetzt die `draft`-Zeilen des Besitzers (Menge = aktuelle Entwurfs-Ids); das Verwerfen oder Bereinigen des Entwurfs (`purge_drafts`) löscht sie.

**Worker `worker/gc.py: gc_media` (arq-Cron täglich 03:50 UTC, Besitzer `backend-mail`):** Markieren-und-Fegen in zwei Läufen. (1) `markdown_image` mit `created_at < now() - 7 Tage`, ohne `media_ref`, ohne `gc_marked_at` bekommen `gc_marked_at = now()`. (2) Zeilen mit `gc_marked_at < now() - 1 Tag`, die immer noch keine `media_ref` haben, werden gelöscht: erst das Objekt im Bucket (`ObjectStorage.remove`), dann die Zeile; ein Speicherfehler lässt die Zeile stehen (nächster Lauf). (3) Zeilen, die wieder referenziert sind, verlieren die Marke. Höchstens 200 Bilder je Lauf. Idempotent, Schlüssel `gc_media:<yyyymmdd>`. `gc_notifications` im selben Modul (2.6). Test mit eingefrorener Zeit (`utcnow`-Hook) und Fake-Storage; ein Bild, das in einer **alten Revision** vorkommt, wird nie gelöscht.

## 9. Tests

Schwellen und Gates wie M3 (Backend: `ruff`, `basedpyright`, Unit, Integration; Frontend: `lint`, `typecheck`, Jest mit 97/94/97/98, `build`; `coverage_critical.py` wächst um `files/attachments`, `files/mime`, `dossier/comments`, `dossier/checklist`, `notifications/service`, `pipeline` bleibt 100 % Branch). Mails: Integrationstests starten Redis (Compose-Dienst) und ersetzen nur den Sender durch `CapturingMailSender`.

### 9.1 Backend, Unit

`test_attachment_readable_truth_table` (Rolle × Sichtbarkeit × Art × Org, Orakel-Tabelle aus 3.7) · `test_attachment_kinds_constraint` · `test_mime_attachment_allowlist` (SVG, GIF, `.docm`, `.exe` als `.png`, `.docx` mit `vbaProject.bin`, `.doc` je 415; `.md/.txt/.csv` mit Binärinhalt 415) · `test_zip_bomb_rejected` · `test_pdf_active_content_rejected` · `test_clean_image_bomb` (40-MP-Bild, `decompression bomb`) · `test_exif_gps_stripped` (Eingabe-JPEG mit GPS-IFD, Ausgabe, Vorschau, Derivate ohne EXIF) · `test_filename_euro_emoji` (`content_disposition("Plakat 5 € 🎬.pdf")` ohne Exception, ASCII-Fallback plus `filename*`) · `test_diff_lines` (Gleichheit, Einfügen, Löschen, Umlaute, CRLF) · `test_checklist_due_rule` (Offset −28, DST-Wechsel 25.10.2026/28.03.2027, ohne Startzeit) · `test_checklist_recompute_skips_manual_done_waived` · `test_template_validation` (vier Katalogpfade ok, `event.raum` unbekannt, `{% if %}` verboten, Filter verboten, Betreff mit LF) · `test_template_render_strict` · `test_notification_recipients` (Tabelle 5.7 je Kind, Selbstausschluss, Organisation `None`) · `test_notification_kinds_essential` · Guards: `open_comment_required`, `no_open_comment_on_hero`, `checklist_done`, `rights_complete` (vier Felder je einzeln), `attachments_scanned`, `flyer_date_confirmed` mit echten Snapshots · `test_snapshot_builders_set_m4_fields` · Reasons-Reihenfolge (M3 2.3) bleibt · `test_media_gc_two_phase` · `test_media_ref_never_removed_while_owner_lives`.

### 9.2 Backend, Integration (`pytest -m integration`, Docker, Redis, MinIO, Postgres)

`test_migrations` (frische DB gleich Upgrade von 0004 mit Bestandszeilen in alten `kind`-Werten und `shared`-Quote; Backfill von `media_ref`) · `test_db_grants` (kein `DELETE` auf `attachment, document, document_revision, comment, quote`; `document_revision` und `comment` Trigger) · `test_attachment_api` (Upload aller erlaubten Arten, Liste, Ersetzen mit `supersedes_id`, Ausblenden, Sichtbarkeit, CHECK-Netz per SQL) · `test_attachment_quarantine` (`pending` 409, `infected` 410, `error` 409 plus `rescan`) · `test_eicar_flow` (EICAR-Datei wird hochgeladen, Worker mit echtem ClamAV: `scan_status = infected`, Objekt weg, Download 410, kein Poster-Guard-Pass) · `test_poster_replace_live` (alter bleibt Hero bis `promote_poster`, dann Tausch, Revision, `public_seq`+1, Feed; infizierter Ersatz lässt das alte Poster unberührt) · `test_attachment_visibility_matrix_http` (Rolle × Org × Route, 404-Regel) · `test_quotes_cross_org_404` (andere Organisation: 404 auf Liste, `select`, `PATCH`, Download der Quote-Datei; `member`/`viewer` gleicher Org: 403; Betrag taucht nirgends sonst auf) · `test_documents_revisions` (`If-Match`, 428, 409 mit `current`, No-op, Diff, Autosave erzeugt keine Revision) · `test_document_body_verbatim` (Korpus) · `test_checklist_template_apply_idempotent` · `test_checklist_due_after_date_change` (PATCH `startsAt` und `postpone` mit Termin: Fälligkeiten verschieben sich, manuelle und erledigte nicht) · `test_t02_blocked_by_required_planning_item` · `test_comments_anchor_validation` · `test_t03_requires_open_comment` · `test_t04_blocked_by_open_hero_comment` (Rückfrage am Poster, nach Poster-Ersatz weiter blockiert, nach `resolve` frei) · `test_mail_templates_api` (Render ok, unbekannter Platzhalter 422 mit `allowed`) · `test_notifications_api` (Inbox, `unread-count`, `read` fremd 404, `read-all`, Prefs, essenziell 422) · `test_notification_fanout` (T02 → Approver und Redaktion, T03 → Organisator:innen, Kommentar, Zuweisung) · `test_mail_requires_redis` (siehe 9.3) · `test_due_reminder_cron_idempotent` · `test_gc_media_worker` · `test_tasks_include_checklist_items` · `test_route_authz_inventory` (alle neuen Routen deklariert) · `test_public_feed_unchanged` (Kanarienvogel: kein Anhangsname, keine Beträge, kein Kommentar im Feed).

### 9.3 Abnahme M4 (wörtlich, PLAN §16.1 Zeile M4, Spalte "Fertig wenn …")

> EICAR in Quarantäne, SVG und `.docm` 415, Bombenbild abgelehnt, `€`/Emoji im Dateinamen ohne 500; Rückfrage am Poster blockiert T04, bis sie gelöst ist; Checkliste aus Kategorie-Vorlage mit neu berechneten Fälligkeiten nach Datumsänderung; Mailvorlage mit Platzhaltern gerendert, unbekannter Platzhalter als Fehler; Roundtrip-Korpus byte-gleich (sonst Textarea Standard); Vergleichsangebote sind für fremde Orgs unsichtbar (Test); Mails gehen nur mit laufendem Redis raus

`backend/scripts/m4_acceptance.py` (Muster `m3_acceptance.py`, gegen den Dev-Stack, nie gegen Live) prüft sie in dieser Reihenfolge und schreibt `docs/M4-ABNAHME.md`:

| # | Prüfpunkt | Beleg |
|---|---|---|
| a | EICAR-Datei hochladen, Worker scannt (ClamAV im Compose), `scanStatus = infected`, Download 410, Liste "Infiziert"; zweite Datei sauber, Download 200 | HTTP + DB |
| b | SVG (mit `<script>`) und `.docm` hochladen: je 415 `unsupported_media_type`; zusätzlich `.docx` mit `vbaProject.bin` 415 | HTTP |
| c | Bombenbild (PNG mit 30 000 × 30 000 Pixeln, wenige KB) 422 `image_rejected`, Worker und API bleiben bei normalem Speicher (Messung) | HTTP + Prozessspeicher |
| d | Datei `Plakat 5 € 🎬.pdf` hochladen und herunterladen: kein 500, Header mit `filename*=UTF-8''…` | HTTP |
| e | Poster mit offener Rückfrage (`anchor.field = hero`): Guard `open_comment_on_hero`, T04 422, Rückfrage lösen, T04 geht; Poster ersetzen löst eine offene Rückfrage nicht | HTTP |
| f | Dossier der Kategorie `party` mit Checkliste aus der Vorlage; `startsAt` um 10 Tage schieben: `checklistRecomputed = n`, `dueAt` aller offenen Vorlagenpunkte verschoben, ein manuell gesetzter und ein erledigter unverändert; offener Pflichtpunkt `planning` blockt T02 mit `checklist_open` | HTTP |
| g | Mailvorlage mit den vier Platzhaltern rendert korrekt (Ortszeit); `{{ event.raum }}` 422 `template_invalid`/`unknown_placeholder` mit Liste | HTTP |
| h | Roundtrip-Gate: `npm run gate:roundtrip`, Ergebnis `passed`/`failed[]` im Protokoll, Standardmodus der Oberfläche danach (Tiptap oder Textarea) im Browser geprüft | Jest + Playwright |
| i | Vergleichsangebote: Dossier der Organisation A; Konto der Organisation B (und `member`) auf Liste, `select`, Datei-Download 404; `viewer` der Organisation A 403; Konto der Organisation A sieht Beträge; Revision, Karten, Feed enthalten keinen Betrag | HTTP |
| j | Mails: mit laufendem Redis erzeugt T02 eine Mail (`CapturingMailSender`) mit Idempotenzschlüssel; Redis angehalten: T02 gelingt, In-App-Eintrag da, Mail verworfen, Warnung im Log ohne Adresse; Redis wieder an | HTTP + Log |
| k | Fälligkeitsmail: Punkt mit Zuweisung und Fälligkeit morgen, Cron von Hand, genau eine Mail, zweiter Lauf keine | arq |
| l | GC: Bild älter als 7 Tage ohne Verweis wird in zwei Läufen gelöscht, Bild aus alter Dokumentrevision bleibt | DB + Bucket |
| m | EXIF: JPEG mit GPS hochladen, Download ohne EXIF-Segment (`exiftool`-Gegenprobe) | Datei |
| n | Mobil (360 px) und Hell/Dunkel: I08 bis I12, I27, I28 ohne horizontales Scrollen, axe grün, Tastaturpfad für Upload und Checkliste | Playwright |

Das Protokoll listet außerdem alle noch offenen M3-Punkte aus `M3-ABNAHME.md` "Offen", die M4 berührt (Platzhalter-Guards jetzt echt; `open_comment_required` mit Zahl statt `None`).

### 9.4 Frontend, Jest und Playwright

Jest: je Reiter eine Spec (Zustände leer, Laden, Fehler, Quarantäne, Konflikt 409, 413/415-Texte), `dossier-markdown-editor` (Umschalter, Autosave-Takt mit gefälschter Zeit, localStorage-Ausfall), `markdown-diff`, `quote-table` (günstigstes, abgelaufen, genau eine Wahl, Währungs-Hinweis), Glocke (Zähler, 99+, Sichtbarkeitsdrosselung), `notification-prefs` (essenziell gesperrt), `roundtrip.gate.spec.ts`, `roundtrip-gate.json`-Aktualitätsprüfung, Contract-Spec zu `bypassSecurityTrustHtml`, Bundle-Test "Tiptap nicht im Initial-Chunk". Playwright `frontend/e2e/m4.spec.ts` (Browser aus `nix build nixpkgs#playwright-driver.browsers`, axe): Poster hochladen mit Pflichtfeldern, Rückfrage am Poster, T04 gesperrt, Rückfrage lösen; Anleitung speichern, Revision, Diff; Checkliste Vorlage anwenden, Datum ändern, Hinweis "n Fälligkeiten neu berechnet"; Mailvorlage Vorschau und Fehler; Glocke und Prefs.

## 10. Abweichungen und offene Entscheidungen

### 10.1 Abweichungen vom PLAN und von M1 bis M3 (zur Nachführung durch Luis)

1. **`attachment.kind`:** `poster, social_post, business_plan, quote, contract, howto_file, other` statt PLAN 3.3 (`poster_print, businessplan, mail_attachment` entfallen, `businessplan` heißt `business_plan`); Bestandsdaten werden umgeschrieben (2.1). Auftrag und Kontrakt gewinnen.
2. **Vergleichsangebote** als Tabelle `quote` mit Datei-Verweis statt `attachment.meta` (PLAN 3.4/7.6): typisierte Beträge, Unique-Index "ein Gewähltes je Gruppe". Die Datei bleibt ein Anhang `kind = quote`.
3. **Mailvorlagen** sind `document`-Zeilen mit `kind = mail_template` (PLAN 7.5) mit Fassade `/mail-templates`; eine eigene Tabelle `mail_template` (PLAN 3.3 "Overrides der Systemmails") legt M4 **nicht** an, weil kein Screen sie verlangt. Systemmail-Texte sind Dateien (`notifications/templates/de`).
4. **Kein Kopf `checklist`:** der Bezug zur angewendeten Vorlage steckt in `checklist_item.template_item_id`; Vorlagen sind Tabellen `checklist_template`/`_item` (PLAN: `checklist_template(_item)`), je Kategorie oder je `required_profile`. Startinhalte sind Vorschlag (D4).
5. **Anker:** `{field}`, `{attachmentId}`, `{checklistItemId}`, `{documentId, rev, from, to}`; keine Spalte `document_id` und kein `offer_id` an `comment`.
6. **Anhangsmetadaten** ohne `If-Match` (letzter Schreiber gewinnt, Audit protokolliert); Dokumente und Dossier behalten ETag.
7. **M3 12.2 geteilt:** `rights_incomplete` prüft Alt-Text, Credit, Rechtegrundlage und Einwilligung (je Feld ein Grund); `image_required` nur noch Existenz, Scan, Derivate. Das SQL-Netz (`attachment_poster_ok`) bleibt unverändert und strenger als die Guards.
8. **`shared`** wirkt in M4 nur innerhalb der eigenen Organisation; Lesen fremder `shared`-Anhänge (PLAN 5.4 Zeile "archiviert") ist M5, weil `load_visible` fremde Dossiers mit 404 verbirgt. Die Funktion `attachment_readable` bildet die Tabelle schon vollständig ab.
9. **Dokumenttyp `retrospective`** steht im CHECK, wird in M4 nicht angelegt: die Quelle bleibt `event.retrospective_md` (M3); die Zusammenführung entscheidet M5 mit T09.
10. **`document.event_id NOT NULL`:** Besitzer `format`/`library`/`offer` kommen mit M5/M7 per Migration (PLAN: `owner_kind, owner_id`); bis dahin kein Polymorphismus ohne Fremdschlüssel.
11. **Poster-Ersatz in `approved`/`live`** (M3 12.6) ist umgesetzt (3.6).
12. **Benachrichtigungs-Kinds:** sieben statt der neun Zeilen aus PLAN 9.4 (`changes_requested` kommt zu den sechs Auftrags-Kinds dazu, weil T03 jetzt real ist und das Kind "nicht abschaltbar" ist; `transition_done` fasst `approved`, `published` und `event_cancelled` für M4 zusammen). `proposal_created`, `edited_after_publish`, `review_overdue`, `followup_reminder`, `import_digest`, `source_failed`, `comment_mention`, `reply` folgen mit M5/M6/B; die M1-Kinds `status_update`, `task`, `comment` entfallen. Erwähnungen (`mentions uuid[]`) legt M4 nicht an.
13. **Mail-Cron stündlich** statt zu einer Berliner Uhrzeit (arq-Cron läuft in UTC, PLAN 17 "zu prüfen"); das Ortsdatum bestimmt der Job.
14. **Mailvorlagen erlauben nur Ausdrücke aus dem Katalog** (keine Anweisungen, keine Filter); strenger als der Upstream, weil Nutzer:innen ohne Admin-Recht schreiben.
15. **Roundtrip-Gate** mit Entscheidungsdatei `roundtrip-gate.json` und Laufzeit-Roundtrip je Dokument (7); Korpus liegt unter `frontend/tests/fixtures/markdown/` (Auftrag nennt `tests/fixtures/markdown/`).
16. **Dokument-Metadaten** (PDF/OOXML-Autor, eingebettete GPS) werden nicht gestrippt (3.5); PLAN 18 Minor 4 gilt damit für Bilder, nicht für Dokumente.
17. **`editor_draft`** trägt auch Dokument-Entwürfe (M3 4.3 sah das vor); `GET /tasks` wächst um Checklistenpunkte (H9).
18. **Größenlimit-CHECK** bildet "Bild 10 MiB, sonst 25 MiB" über den MIME-Typ ab; ein Bild als `other` bleibt bei 10 MiB.
19. **Größen-CHECK als `CASE`** (Integrationslauf): Bild bis 10 MiB, sonst bis 25 MiB. Eine `OR`-Fassung hätte Bilder bis 25 MiB durchgelassen.
20. **`social_post` braucht `meta.channel`** beim Upload (422 sonst); der Upload-Dialog fragt den Kanal ab.
21. **Gate-Regel vor 404 (M2 Abschnitt 4):** 9.3 (i) nennt für `member` auf `select` 404; `member` hat `dossier.attach` nirgends, das Routen-Gate antwortet deshalb 403 `forbidden` vor jeder Objekt-ID (kein Existenzhinweis). Lesende Routen (Liste, Datei-Download) bleiben 404. Das Abnahme-Skript prüft so.
22. **`render-preview` mit `docId = new`** rendert den ungespeicherten Entwurf einer neuen Vorlage (Leserecht des Dossiers); der Editor zeigt die Vorschau vor dem ersten Speichern. Eine ungültige Id ist 404.
23. **Poster-Mindestgröße (D6) wirkt auf M1 bis M3:** Testbilder und `m3_acceptance.py` laden 1400 × 900 statt 640 × 480 hoch; T03 braucht seit M4 eine offene Rückfrage, `m3_acceptance.py` schreibt sie vor T03 (wie der Dialog, 4.2).

### 10.2 Entscheidungen für Luis (Vorschläge, nicht belegt)

- **D1 Auflösen von Rückfragen:** **Autor:in, `approver` und `editor` dürfen auflösen**, Organisator:innen nicht, damit die Prüfenden die Rückfrage am Poster nicht selbst wegklicken können. Alternative: jede Person mit `comment.write` in der Organisation darf auflösen (weniger Reibung, schwächere Vier-Augen-Wirkung).
- **D2 Wer sieht Vergleichsangebote:** **`submitter` aufwärts der eigenen Organisation, `stupa`, `editor`, `admin`**; `viewer` und `member` nicht (PLAN: "Org-Rollen"). Alternative: nur `organizer` aufwärts.
- **D3 Gleiche Organisation ohne Recht antwortet 403, nicht 404** (kein Existenzschutz innerhalb der Organisation).
- **D4 Checklisten-Seeds** (2.4) sind Startvorschlag; Luis oder die Redaktion prüfen Texte, Phasen, Pflichtkennzeichen und Offsets, bevor der Pilot sie sieht.
- **D5 Platzhalter-Katalog** v1 hat nur die vier PLAN-Pfade; Vorschlag: `event.ends_local`, `event.summary`, `org.short`, `venue.address` ergänzen (alle öffentlich oder organisationsintern, keine Personendaten).
- **D6 Poster-Mindestgröße 1200 px** (aus dem I08-Fehlertext) wird als harte Regel (422) umgesetzt; Alternative: Warnung.
- **D7 Hinweis statt Sperre bei `shared` für Dokumente** (3.5); Alternative: Dokumente nie `shared` bis zu einem Metadaten-Strip.

## 11. Verzeichnisbesitz

Drei Builder, jeder schreibt nur in seinen Bereich. Konflikte löst die Orchestrierung. Kopien aus Upstream mit Kopf `Copied from STUPA-Workflow@93c33d6 <pfad>` (Nachbauten "Pattern from") und Eintrag in `PROVENANCE.json` (Modus `U`); nichts wird übernommen, ohne dass der Builder die Quelle gelesen hat. Kein Commit und kein Push vor dem Review; im letzten Schritt entsteht `feat/m4-dossier` mit gescopten Commits (`feat(files)`, `feat(dossier)`, `feat(notifications)`, `feat(worker)`, `feat(frontend)`, `test`, `docs`). Kein Eingriff in Live-Systeme. Werkzeuge: `nix run nixpkgs#ruff`/`#basedpyright`, `pytest` mit `LD_LIBRARY_PATH` (libstdc++, libmagic), Playwright-Browser über `nix build nixpkgs#playwright-driver.browsers`; Dev-Stack (`deploy/docker-compose.dev.yml`), Units `stupa-api`/`stupa-worker` per `systemctl --user restart`, `ng serve :4200`.

| Builder | Besitzt | Aufgaben |
|---|---|---|
| **backend-dossier** | `backend/app/modules/{dossier,files,media}/**`, Migration `0005_dossier_knowledge` samt `models.py`-Anteilen dieser Module (`files/models.py`, `media/models.py`, neu `dossier/{models_documents,models_comments,models_checklist,models_quotes}.py` bzw. entsprechende Dateien), dazugehörige Tests (`tests/unit/{dossier,files,media}`, `tests/integration/dossier`), `seeds/checklists.yaml` und der Seed-Lader | Abschnitte 2.1 bis 2.5, 2.7 (Tabellen), 3, 4 (Daten), 5.1 bis 5.6, 5.8, 8 (Router, `media_ref`); `worker/dossier`-Jobs `promote_poster` und Vorschau (in `dossier/worker_jobs.py`) |
| **backend-dossier** (kleine Hook-Ausnahmen außerhalb der Module, nur diese Stellen) | `pipeline/{guards/content.py, guards/media.py, snapshot.py, reasons.py}`, `events/{card_extras.py, writer.py, access.py}` (nur Snapshot-Daten, `recompute_due`-Aufruf, `media_ref`), `tasks/service.py` (Abschnitt `checklist_item`), `shared/filenames.py` falls nötig, `audit/actions.py` (neue Aktionen), `api_routers.py`, `deploy/db/roles.sql`, `deploy/nginx` (Location 26 MiB), `docs/M4-ABNAHME.md`, `scripts/m4_acceptance.py`, `scripts/coverage_critical.py`, `.claude/skills/{be-events,be-pipeline}/SKILL.md`, `CLAUDE.md`, `README.md` | Tabelle 4; Aufrufe an `notifications.service.notify` an den Stellen aus 5.7; Skill-Pflege; Abnahme-Skript |
| **backend-mail** | `backend/app/modules/{notifications,account}/**` (`account` neu: `notification-prefs`-Router, Schemas, Service), `backend/worker/{mail,gc}.py`, `worker/main.py` (Cron-Einträge), Templates `notifications/templates/de/**`, Tabellen `notification`, `notification_pref` (Modelle in `notifications/models.py`; DDL steht in Migration 0005, die `backend-dossier` führt, `backend-mail` liefert ihr den Abschnitt 2.6 als Modell zuerst), dazugehörige Tests (`tests/unit/notifications`, `tests/integration/notifications`) | Abschnitte 2.6, 5.7, 8 (GC-Worker), `kinds.py`, `recipients.py`, `service.notify`, Mailqueue-Verdrahtung (`NullMailQueue`), Fälligkeits-Cron, `gc_media`, `gc_notifications`, `.claude/skills/be-notifications/SKILL.md` (neu) |
| **frontend** | `frontend/**` | Abschnitte 6 und 7: Reiter I08 bis I12, `dossier-markdown-editor`, `shared/markdown/*`, `shared/ui/{history,chat,markdown-diff,quote-table}`, Glocke und Inbox (I28), Konto-Abschnitt (I27), Alias und Jest-Mapper für den Kit-Entry, Korpus und Gate-Skript, `frontend/e2e/m4.spec.ts`, i18n, `PROVENANCE.json`-Einträge der Kopien, `.claude/skills/frontend/SKILL.md` |

Schnittstellen (gemeinsamer Vertrag, Reihenfolge): (1) `backend-mail` liefert zuerst `kinds.py`, `notifications/models.py` und die Signatur `notify(session, kind, recipients, event, params, dedupe_key)` samt `recipients_for(kind, event, actor)`; (2) `backend-dossier` schreibt die Migration `0005` mit allen Tabellen aus Abschnitt 2 und liefert danach Anhänge, Kommentare und Guards (5.1, 5.5, 4); (3) danach Dokumente, Checkliste, Mailvorlagen, Angebote; (4) das Frontend baut gegen den laufenden Dev-Stack und gegen `HttpTestingController`-Antworten und beginnt mit `shared/markdown`, dem Korpus und dem Gate-Skript, weil dessen Ergebnis den Standardmodus des Editors bestimmt. Keine Datei in `.github/**` ändert sich; CI ruft die bestehenden Jobs auf (der Playwright-Lauf mit axe bleibt ein manuelles Gate gegen den Dev-Stack, M3 9.5).


## Nachträge aus dem Review (Fix-Runde)

- **Bildverweise.** `media_ref.owner_type` kennt `event`, `document`, `comment`, `draft`. Anlegen eines Dossiers, Kommentare und Editor-Entwürfe des Dossiers (`owner_kind = event`, Owner-ID wie bei Dokument-Entwürfen über `draft_owner_id`) schreiben Verweise; Löschen oder Bereinigen eines Entwurfs räumt sie weg. `gc_media` sperrt die Bildzeile (`FOR UPDATE`) und prüft den Verweis erneut, bevor das Objekt gelöscht wird.
- **Mailvorlagen** werden nur über `/events/{id}/mail-templates/...` geschrieben. `PUT /documents/{id}` auf ein Dokument der Art `mail_template` ergibt 409 `use_mail_templates`. Der Entwurfsspeicher bleibt offen (er verändert das Dokument nicht, das Speichern validiert). `PUT /documents/{id}` liest höchstens 1,5 MiB.
- **Checkliste.** `required`, `text` und `phase` eines Vorlagenpunkts sind unveränderlich (409 `template_item`); der Audit-Eintrag eines Patches nennt alten und neuen Wert von `required`. Zuständig können nur Mitglieder mit Bearbeitungsrecht (`submitter`, `organizer`, `approver`) und Redakteur:innen sein.
- **Scan.** Eine Ersatzdatei (nicht Plakat) blendet ihren Vorgänger erst nach sauberem Scan aus. `POST /attachments/{id}/rescan` gilt auch für `pending` älter als 10 Minuten; der Worker-Cron `requeue_stale_scans` reiht solche Zeilen alle zehn Minuten neu ein. Scheitert das Einreihen nach dem Commit, antwortet der Upload trotzdem 201.
- **Ersetzen.** `personsDepicted` wird beim Ersetzen nur übernommen, wenn es fehlt; ein gesendetes `false` schaltet es aus und verwirft den alten Einwilligungsvermerk. Umbenennen ändert die Dateiendung nie (422 `extension_changed`). `.docx/.xlsx/.pptx` speichern den OOXML-Typ statt `application/zip`.
- **Archive.** Die entpackte Größe wird beim Lesen gemessen (Obergrenze 200 MiB und 100:1). ODT mit `Basic/`, `Scripts/`, `Object ` oder `<script:` ist 415.
- **Benachrichtigungen.** `comment_added` erreicht frühere Kommentierende nur, solange sie das Dossier noch lesen dürfen (Mitglied der Organisation, Redaktion, `stupa`, Eigner:innen). `notification.params` enthält nur Anzeigewerte; `itemText` geht nur in die Mail. Ein gescheitertes Einreihen gibt den Redis-Anspruch `notif:<id>:mail` frei. `send_due_reminders` läuft ohne Queue nicht. `PrefOut` trägt `mailAvailable`; I27 zeigt für Arten ohne Mail keinen Mail-Schalter.
- **Vergleichsangebote.** `select_quote` nimmt vorab eine Transaktionssperre je Dossier und Gruppe, parallele Auswahlen laufen nacheinander.
- **Kommentare.** Threads, die an einer eingeschränkten Datei (Angebot, Businessplan, Vertrag) hängen, sehen nur Personen, die die Datei sehen dürfen. Auflösen dürfen Autor:in und `event.approve`.
- **Posteingang (I28)** hält `nextCursor` und lädt ältere Einträge nach.
- **Bekannte Grenze.** `GET /media/images/{id}` verlangt nur `library.read`; Bilder in privaten Kommentaren oder `team`-Dokumenten sind für jede angemeldete Person lesbar, die die unratbare Uuid kennt (wie im Upstream). §5.4 "andere Organisation: nie" gilt damit für das Dossier, nicht für eingebettete Bilder. Ob das so bleibt oder `media_ref` den Besitz prüfen soll, ist offen und gehört in `ENTSCHEIDUNGEN.md`.
