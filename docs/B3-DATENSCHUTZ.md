# B3: Unterlage für die Datenschutzbeauftragte (Gate B3)

Stand 2026-10-24. Vorlage zur Durchsicht, kein Beschluss. Gate B3 verlangt eine schriftliche Rückmeldung der
Datenschutzbeauftragten zu Löschkonzept, Einwilligungstext, Double-Opt-in und Listmonk-Betrieb (PLAN 16.2, W3).
B3 wartet darauf nicht: ohne Rückmeldung gilt B3 als technisch fertig, das Gate bleibt offen und der Go-live (B5)
gesperrt. Die Datenschutzerklärung selbst entsteht in B5; hier steht nur, was die Technik tut.

## 1. Welche Daten entstehen

| Wer | Was | Wo | Wie lange |
|---|---|---|---|
| Kalender-Profil (ohne Mail) | Antworten des Fragebogens (Interessen, Kategorien), Hash des Kalender-Tokens, Datum des letzten Abrufs. Keine Adresse, keine IP | Postgres, Tabelle `subscription_profile` | bis 12 Monate nach dem letzten Abruf, dann gelöscht |
| Mail-Abo, unbestätigt | Adresse (verschlüsselt, `pgcrypto`), Hash der Adresse, Hash des Bestätigungslinks, Einwilligungstext-Version, Zeitpunkt | Tabelle `subscriber`, Status `pending` | 48 Stunden, dann gelöscht; der Link gilt 24 Stunden |
| Mail-Abo, bestätigt | wie oben plus Zeitpunkt der Bestätigung (Nachweis des Double-Opt-in), Kategorien, die der Einwilligungstext nannte | `subscriber` und `subscription_profile`, Status `confirmed` | bis zur Abmeldung |
| Abgemeldet | wie bestätigt | Status `unsubscribed` | 30 Tage, dann anonymisiert (siehe 3) |
| Abo-Aufträge an Listmonk | Auftragsart, Zeitstempel, bei Löschaufträgen die verschlüsselte Adresse bis zur Ausführung | Tabelle `outbox` | erledigte Aufträge 30 Tage |

Nicht gespeichert: IP-Adressen und User-Agent im Datensatz, Klartext-Adressen, Tokens im Klartext (nur SHA-256), Adressen
oder Tokens in Logs. Die Adress-Limits arbeiten mit einem Hash und stehen nur kurz in Redis (24 Stunden).

## 2. Was an Listmonk geht

Nur nach bestätigter Einwilligung (Double-Opt-in, siehe 4) und nur für die Zustellung der Wochenmail:

- Adresse (Klartext, Listmonk braucht sie zum Senden),
- Namensfeld mit fester Beschriftung „STUPA Events Abo“ (kein Personenname),
- Mitgliedschaft in Listen: eine Liste „alle“ und je gewählter Kategorie eine Liste (`events-<Kategorie>`),
- Attribute: `source` (`get-started`), `profile_version`, `profil_id` (interne Kennung des Profils), `kategorien`.

Listmonk sendet nie selbst eine Bestätigungsmail (die Listen sind Single-Opt-in, die Einwilligung liegt bei uns;
getestet gegen Mailpit). Jede Kampagnenmail trägt `List-Unsubscribe` mit One-Click und einen Abmeldelink im Text.
Die Wochenmail liegt als Entwurf in Listmonk und wird erst nach einem Freigabeklick einer Person mit dem Recht
`digest.release` gesendet.

## 3. Löschkonzept (PLAN 8.9)

Personendaten verlassen die Datenbank nur über Funktionen `privacy_*` (`SECURITY DEFINER`); die Rolle der Abo-Routen hat
kein `DELETE`. Täglich 03:20 UTC läuft der Job `purge_expired`:

| Funktion | Wirkung | Frist |
|---|---|---|
| `privacy_purge_pending` | löscht unbestätigte Anmeldungen; ein verknüpftes Profil bleibt als reines Kalender-Profil | 48 Stunden |
| `privacy_anonymize_unsubscribed` | Adresse, Hash, Tokens und Kategorien werden überschrieben, das Profil gelöscht; zurück bleibt eine Zeile ohne Personenbezug (`erased`); der Listmonk-Datensatz wird gelöscht | 30 Tage nach Abmeldung |
| `privacy_purge_profiles` | löscht Kalender-Profile ohne Abruf | 12 Monate |
| `privacy_purge_outbox` | löscht erledigte Aufträge | 30 Tage |

Jeder Lauf mit Treffern schreibt einen Audit-Eintrag mit Aktion und Zähler, ohne Personenbezug.

Auf Verlangen: „Alles abbestellen und Daten löschen“ auf der Verwaltungsseite löscht sofort Adresse, Profil und Tokens und
reiht die Löschung des Listmonk-Datensatzes ein (läuft Listmonk nicht, bleibt der Auftrag mit der verschlüsselten Adresse
liegen und wird wiederholt; ein toter Löschauftrag ist ein Alarm mit Frist von 24 Stunden). Die Auskunft nach Art. 15
DSGVO liefert eine Admin-Funktion (`POST /api/admin/subscribers/lookup`), die Löschung eine zweite (`…/erase`); beide
antworten nie mit der Adresse im Klartext.

## 4. Einwilligung und Double-Opt-in

Einwilligungstext, Version `2026-10-1` (festgeschrieben, spätere Änderungen sind neue Versionen, die alten bleiben
im Code und im Golden-Test):

> Ich möchte wöchentlich eine Mail zu {Kategorien}. Abmelden geht jederzeit mit einem Klick.

`{Kategorien}` sind die Bezeichnungen der gewählten Interessen. Daneben ein Link zur Datenschutzerklärung und der
Hinweis „Wir schicken dir eine Bestätigung. Ohne Bestätigung speichern wir nichts.“ (nach 48 Stunden stimmt das auch
technisch).

Ablauf:

1. Fragebogen, Adresse und Häkchen, Prüfung gegen Spam (ALTCHA, kein Fremdanbieter) und Limits (10 Anmeldungen je IP und Stunde,
   höchstens 3 Abo-Mails je Adresse und Tag).
2. Die Antwort ist für bekannte und unbekannte Adressen gleich (Inhalt und Antwortzeit); es gibt keinen Hinweis,
   ob eine Adresse schon angemeldet ist.
3. Mail mit Bestätigungslink (24 Stunden gültig, einmalig). Der Link öffnet eine Seite; **erst der Knopf „Abo bestätigen“
   (POST) bestätigt.** Ein bloßes Öffnen oder ein Link-Scanner der Hochschulmail ändert nichts.
4. Nachweis: Zeitpunkt der Einwilligung, Zeitpunkt der Bestätigung, Textversion und Kategorien.
5. Wer eine schon bestätigte Adresse erneut anmeldet, ändert nichts an den Listen; die Adresse bekommt nur eine Mail
   mit Verwaltungslink. So kann niemand fremde Adressen auf zusätzliche Listen setzen.
6. Abmeldung gilt endgültig: Wer sich in Listmonk oder auf der Verwaltungsseite abmeldet, wird nie wieder ohne neue
   Bestätigung angeschrieben (der tägliche Abgleich übernimmt Abmeldungen aus Listmonk).

## 5. Fragen an die Datenschutzbeauftragte

1. Reicht die Frist von 30 Tagen zwischen Abmeldung und Anonymisierung (Nachweis der Abmeldung, Beschwerde), oder soll
   sie kürzer oder länger sein?
2. Ist die Aufbewahrung der Einwilligungs- und Bestätigungszeitpunkte (ohne Adresse) in der anonymisierten Zeile
   über die Abmeldung hinaus unbedenklich?
3. Listmonk-Betrieb (W3): Wer betreibt die Instanz, wo steht sie, gibt es einen Auftragsverarbeitungsvertrag? Die
   Technik nimmt Listmonk extern an (https, feste Host-Liste).
4. Absenderdomain und -adresse der Wochenmail (SPF, DKIM, DMARC) und Impressumsangaben im Mailfuß.
5. Soll die Datenschutzerklärung die Kategorien-Wahl als Profiling im Sinn von Art. 4 Nr. 4 DSGVO nennen? Es entsteht
   kein Personenbezug außerhalb der Mail-Abos; das Kalender-Profil hat keine Adresse.
6. Wer ist Ansprechperson für Auskunfts- und Löschverlangen, und genügt die Admin-Funktion als Verfahren?

## 6. Rückmeldung

Offen. Eintrag in `docs/B3-ABNAHME.md`, sobald die Rückmeldung vorliegt.
