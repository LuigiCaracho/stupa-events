# Geheimnisse und Schlüssel

Nur Namen, Erzeugung und Rotation. Werte stehen nie im Repo; `deploy/.env.example` zeigt die Schlüsselnamen,
`deploy.sh` bricht bei jedem übrig gebliebenen `CHANGE_ME` ab. Jeder Wert ist frisch und nie gleich dem eines
anderen Dienstes (Workflow-Tool eingeschlossen).

## Abos und Listmonk (B3)

| Name | Zweck | Erzeugen | Rotation |
|---|---|---|---|
| `EVENTS_SUBS_PASSWORD` | Passwort der DB-Rolle `events_subs` (nur Abo-Tabellen, kein `DELETE`) | `openssl rand -base64 24` | frei: `ALTER ROLE events_subs PASSWORD …`, dann `SUBS_DATABASE_URL`, API und Worker neu starten |
| `PGCRYPTO_EMAIL_KEY` | Schlüssel von `pgp_sym_encrypt` für `subscriber.email_enc` (mind. 32 Zeichen) | `openssl rand -base64 48` | **nicht ohne Migration**, siehe unten |
| `EMAIL_HASH_KEY` | HMAC-Schlüssel für `email_hmac` und den Adress-Limiter (mind. 32 Zeichen, anders als der erste) | `openssl rand -base64 48` | **nicht ohne Migration**, siehe unten |
| `ALTCHA_HMAC_SECRET` | signiert die ALTCHA-Aufgaben; der Container `altcha` teilt ihn | `openssl rand -hex 24` | frei: neuen Wert setzen, API und `altcha` neu starten; offene Aufgaben (5 Minuten) werden ungültig |
| `ALTCHA_ROOT_PASSWORD` | erster Login des ALTCHA-Dashboards (nur Compose) | `openssl rand -base64 18` | im Dashboard ändern |
| `LISTMONK_API_USER`, `LISTMONK_API_TOKEN` | API-Nutzer von Listmonk (Header `Authorization: token USER:TOKEN`) | in Listmonk unter Users einen Nutzer vom Typ API anlegen; das Token zeigt Listmonk nur beim Anlegen | neuen API-Nutzer anlegen, Token eintragen, API und Worker neu starten, alten Nutzer löschen |
| `LISTMONK_URL`, `LISTMONK_ALLOWED_HOSTS` | Ziel des Clients: nur `https`, Host muss in der Liste stehen | Betreiber | bei Umzug beide ändern |

Die Dev-Werte stehen in `deploy/.env.host.example`; `deploy/listmonk-seed.sh` legt den Dev-API-Nutzer an und schreibt
dessen Token in `backend/.env`.

### Rechte des Listmonk-API-Nutzers (Weiche B3-3)

Der Nutzer braucht eine Benutzerrolle mit genau diesen Rechten: `subscribers:get`, `subscribers:get_all`,
`subscribers:manage`, `campaigns:get`, `campaigns:get_all`, `campaigns:manage`, `campaigns:manage_all`,
`lists:get_all`, `lists:manage_all`. **Nie** `subscribers:sql_query` (der Client sucht über `search`, nicht über die
SQL-Abfrage), nie `settings:*`, `users:*`, `tx:send`. Listmonk kennt Listen-Rollen nur mit konkreten Listen-IDs,
nicht mit einem Muster `events-*`. Der Client legt neue Listen selbst an (`lists:manage_all` nötig); wer das nicht
will, legt die Listen `events-alle` und `events-<Kategorie>` von Hand an und vergibt eine Listen-Rolle. Dann muss
für jede neue Kategorie die Rolle von Hand ergänzt werden, sonst scheitert der Outbox-Auftrag `ensure_list` und
steht auf `dead`.

### Schlüssel `PGCRYPTO_EMAIL_KEY` und `EMAIL_HASH_KEY` rotieren

Beide hängen an den gespeicherten Daten. Ein neuer Wert ohne Umrechnung macht alle Adressen unlesbar beziehungsweise
unauffindbar. Verfahren (Wartungsfenster, Worker und API angehalten):

1. Sicherung der Datenbank.
2. Beide Schlüssel alt und neu bereitstellen. In einer Transaktion, als `events_migrator`:
   `UPDATE subscriber SET email_enc = pgp_sym_encrypt(pgp_sym_decrypt(email_enc, :alt), :neu)` für alle Zeilen mit
   `email_enc IS NOT NULL`; in derselben Transaktion `email_hmac` neu berechnen (HMAC-SHA-256 über die kanonische
   Adresse mit dem neuen `EMAIL_HASH_KEY`, in Python, weil die Kanonisierung dort liegt) und die offenen
   Outbox-Aufträge `delete` mit `payload.emailEnc` ebenso umschlüsseln.
3. `.env` auf die neuen Werte, API und Worker starten, `reconcile_listmonk` einmal von Hand laufen lassen.
4. Alte Werte vernichten.

Die Postgres-Rolle `events_subs` setzt `log_parameter_max_length = 0`, damit der Schlüssel als Bind-Parameter nicht in
einem Fehlerlog des Servers steht.
