---
name: be-notifications
description: Notifications, mail, inbox, account prefs, user mail templates and GC workers of the backend. Use when touching app/modules/notifications, app/modules/account, worker/mail.py or worker/gc.py.
---

# Notifications (M4, cut to four kinds in M5b)

- Kinds: `notifications/kinds.py`: `comment_added`, `published`, `cancelled`, `checklist_due`, all with mail, none essential. `published` reaches the editorial team and the members of the organization, `cancelled` also the creator (`recipients.py`); the acting person never gets their own.
- Hook for other modules: `notify(session, kind, recipients, event, params, dedupe_key, actor_sub=...)` or `notify_event(...)` (resolves group kinds via `recipients_for`). It inserts inbox rows in the caller's transaction and returns `PendingMail`s. After `commit()` call `dispatch_mails(app.state.arq_pool, pending)`. Redis missing means the mail is dropped with a warning (no address), never a 500.
- `params` hold display values only (`actorName`, `dueDate`), never comment text or `itemText` (free text goes into the mail only). `dedupe_key` is stored as `<key>:<sub>`.
- System mail templates: `notifications/templates/de/<kind>.{subject,txt,html}.j2`, Jinja sandbox, `StrictUndefined`. A new mail kind needs all three files plus a `Kind` entry and a CHECK update in a migration.
- User templates (dossier `mail_template`): `placeholders.validate_template` / `preview.render_preview`; only `{{ path }}` from `CATALOG`; failures are 422 `template_invalid` with `reasons[]` (`unknown_placeholder` carries `field`, `allowed`).
- Workers: `send_due_reminders` (hourly :10, tomorrow in Europe/Berlin, `notified_due_for`), `gc_media` (03:50, two phases, `gc_marked_at`), `gc_notifications` (03:40, read rows > 90 days).
- Tests: `tests/unit/notifications`, `tests/integration/notifications` (real Postgres; mails via `FakePool` + `CapturingMailSender`).
