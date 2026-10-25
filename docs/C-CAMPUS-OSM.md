# Campuskarte: OSM-Prüfschritt

Einmalige Abfrage der Gebäudeumrisse am Campus Alteburgstraße 150, Reutlingen, für `backend/seeds/campus.geojson` (Tabelle `campus_building`, Migration `0013_maps`). Zur Laufzeit hängt nichts an OSM: die API liest nur die Tabelle.

**Attribution:** © OpenStreetMap-Mitwirkende, Daten unter der ODbL 1.0 (https://www.openstreetmap.org/copyright). Der Fuß der Campuskarte nennt sie. Ob die abgeleiteten Polygone (eine Datenbank im Sinne der ODbL) Share-Alike auslösen, ist rechtlich nicht geprüft (Weiche W-C7).

## Abfrage

Datum 2026-10-25, Overpass-API `https://overpass-api.de/api/interpreter` (POST), Stand der OSM-Daten `2026-10-25T13:04:21Z`.

```
[out:json][timeout:25];
way["building"](48.4785,9.1790,48.4865,9.1945);
out geom tags;
```

Der Entwurf aus dem Kontrakt 4.6 (Anker über `around.anchor:400` mit Adressen und Relationen) lief zweimal in den Serverfehler `Query timed out after 97 seconds` (kein Ergebnis, 13:55 und 14:03). Statt eines dritten Versuchs mit derselben Abfrage wurde die Suche auf eine Bounding Box um den Campus verkleinert (rund 0,9 km mal 1,2 km, nur Ways). Die Abfrage wurde damit insgesamt dreimal an Overpass gestellt, die dritte lieferte 430 Gebäude.

## Zuordnung Nummer zu Umriss

Nur über das Tag `name` der Form `Gebäude <N>` (ein Umriss je Nummer), nie geraten. Fälle mit widersprüchlichen Tags bleiben draußen.

| Gebäude | OSM | Quelle | Bemerkung |
|---|---|---|---|
| 1 | way/27246976 | OSM-Tag `name` | Maschinenhalle |
| 2 | way/27246974 | OSM-Tag `name` | |
| 3 | way/27246971 | OSM-Tag `name`, `addr:housename` | Präsidium |
| 4 | way/27246970 | OSM-Tag `name`, `addr:housename` | |
| 5 | way/27246975 | OSM-Tag `name` | |
| 6 | way/27246969 | OSM-Tag `name`, `addr:housename` | Aula |
| 7 | way/27246968 | OSM-Tag `name`, `addr:housename` | Kantine (`amenity=canteen`) |
| 8 | way/27304282 | OSM-Tag `name`, `addr:housename` | |
| 9 | way/290446675 | OSM-Tag `name`, `addr:housename` | Pflicht für C4. Zwei weitere Ways (290589845 mit `Alteburgstraße 150` und `Bau 9`, 584490756 mit `layer=2`) haben dieselbe Ausdehnung und sind Gebäudeteile; sie fügen keine Fläche hinzu. |
| 10 | way/27246967 | OSM-Tag `name` | |
| 12 | way/152573262 | OSM-Tag `name` | `alt_name` ESB Learning-Factory |
| 13 | way/62473921 | OSM-Tag `name`, `addr:housename` | Kindertagesstätte |
| 14 | way/152573265 | OSM-Tag `name`, `addr:housename` | |
| 15 | way/27246977 | OSM-Tag `name` | |
| 16 | way/354147961 | OSM-Tag `name`, `addr:housename` | |
| 18 | way/192964705 | OSM-Tag `name` | Center for Entrepreneurship |
| 20 | way/62364195 | OSM-Tag `name`, `addr:housename` | |
| 21 | way/1108293600 | OSM-Tag `name` | Werk 150 |
| 30 | way/1108293602 | OSM-Tag `name` | Texoversum |
| 11 | way/152573260 | **fehlt (Konflikt)** | `name` sagt "Gebäude 11 - Mensa", `addr:housename` sagt "Gebäude 14", und Gebäude 14 hat einen eigenen Umriss. Nicht übernommen. |
| 17 | **fehlt** | **fehlt** | In OSM gibt es keinen Umriss mit der Nummer 17 (auch keinen Pavillon). Das Seed nennt "Raum 17-U14", "Campus Reutlingen Building 17" und "Geb. 17 Pavillon"; diese Orte bleiben ohne Gebäudepolygon. |

Handpolygone (`approx: true`) gibt es nicht: der Builder hat keinen Luftbildzugriff und rät keine Koordinaten (Weiche W-C4). Alle 19 Polygone sind `approx = false`.

## Beobachtung zum Seed

Gebäude 9 trägt in OSM die Adresse Alteburgstraße 150 (Bau 9). Das Seed der Orte nennt für `Kinosaal 9-133` und `Fakultät Informatik` die Pestalozzistraße 62; die Zuordnung zum Polygon läuft aber über `venue.building_no`, nicht über die Adresse.
