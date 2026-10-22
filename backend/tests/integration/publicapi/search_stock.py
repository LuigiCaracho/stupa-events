"""The fixed stock of the 20 sample searches (contract 6.4), built through the API."""

from __future__ import annotations

from tests.integration.events.harness import Api
from tests.integration.publicapi.site_data import Site, add, at

STOCK = (
    ("movie", "Movienight: Whiplash", "Kino im Hörsaal", "kino", "fsi"),
    ("fsi", "Sitzung der Fachschaft FSI", "Planung des Semesters", "sitzung", "fsi"),
    ("stupa", "STUPA-Sitzung", "Gebäude 9, Raum 133", "sitzung", "stupa"),
    ("caipi", "CaIPi-Night", "Party mit DJ", "party", "fsi"),
    ("karaoke", "Karaoke im Rappen", "Singen bis spät", "get-together", "makers"),
    ("ski", "Skiausfahrt Arlberg", "Skifahren in den Alpen", "skiausfahrt", "makers"),
    ("skydive", "Skydiving Tandemsprung", "Mit dem Fallschirm", "skydiving", "makers"),
    ("presidium", "Offenes Präsidium", "Kaffee mit dem Präsidium", "sitzung", "stupa"),
    ("culture", "Culture Chill & Chat", "Entspannt reden", "get-together", "fsi"),
    ("repair", "Repair Café", "Reparieren statt wegwerfen", "repair-cafe", "makers"),
    ("kart", "Kart fahren", "Auf der Kartbahn", "kart-fahren", "fsi"),
    ("campus", "Campusfest 2026", "Das große Fest", "campusfest", "stupa"),
)
USERS = {"fsi": "organizer-fsi", "makers": "organizer-makers", "stupa": "organizer-stupa"}


async def seed_stock(api: Api) -> Site:
    """Publish the stock, one event a day from tomorrow on."""
    site = Site()
    for index, (key, title, summary, category, org) in enumerate(STOCK, start=1):
        await add(
            api,
            site,
            key,
            title=title,
            summary=summary,
            org=org,
            user=USERS[org],
            primaryCategoryId=api.category_ids[category],
            **at(index),
        )
    return site
