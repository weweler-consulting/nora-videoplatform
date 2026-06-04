"""Seed der zwei Check-In-Templates (start, laufend).

Idempotent: legt ein Template nur an, wenn für seinen `typ` noch keines existiert.
Re-Runs sind ein No-op und überschreiben NICHT, was Nora im Admin editiert hat.
Die Texte/Optionen leben damit in der DB (editierbar), nicht hartkodiert im Player.
"""
import logging
import uuid

from sqlalchemy import select

from app.core import db as db_module
from app.models.checkin import CheckinTemplate, CheckinStep

logger = logging.getLogger(__name__)

_HAEUFIGKEIT = ["täglich", "mehrmals pro Woche", "selten", "nie"]

# typ -> (name, [steps]). Jeder Step: dict mit key/typ/frage und optionalen Feldern.
TEMPLATES: dict[str, tuple[str, list[dict]]] = {
    "start": (
        "Bestandsaufnahme",
        [
            {"key": "intro", "typ": "intro",
             "frage": "Schön, dass du dabei bist. Bevor wir starten: 3 Minuten für deine Bestandsaufnahme."},
            {"key": "warum", "typ": "langtext",
             "frage": "Warum bist du hier? Was hat dich gerade jetzt dazu gebracht, zu starten?"},
            {"key": "hauptziel", "typ": "mehrfachauswahl", "pflichtfeld": True,
             "frage": "Was möchtest du in den 4 Wochen erreichen?",
             "optionen": ["Blutzucker stabilisieren", "Gewicht entspannt regulieren", "Mehr Energie",
                          "Heißhunger in den Griff bekommen", "Sicherheit beim Essen"]},
            {"key": "ziel_konkret", "typ": "langtext",
             "frage": "Woran würdest du in 4 Wochen merken, dass sich etwas verändert hat?"},
            {"key": "energie", "typ": "skala", "pflichtfeld": True,
             "frage": "Wie ist deine Energie im Alltag aktuell?",
             "skala_min": 1, "skala_max": 10,
             "skala_labels": {"min": "sehr niedrig", "max": "sehr hoch"}},
            {"key": "nachmittagstief", "typ": "einfachauswahl", "pflichtfeld": True,
             "frage": "Wie oft erwischt dich ein Nachmittags- oder Energietief?",
             "optionen": _HAEUFIGKEIT},
            {"key": "heisshunger", "typ": "einfachauswahl", "pflichtfeld": True,
             "frage": "Wie oft hast du Heißhunger?",
             "optionen": _HAEUFIGKEIT},
            {"key": "fruehstueck_status", "typ": "einfachauswahl", "pflichtfeld": True,
             "frage": "Wie sieht dein Frühstück gerade meistens aus?",
             "optionen": ["süß, z. B. Müsli/Marmeladenbrot", "herzhaft & eiweißreich",
                          "sehr wenig oder gar nichts", "ganz unterschiedlich"]},
            {"key": "herausforderung", "typ": "langtext",
             "frage": "Was ist deine größte Herausforderung rund ums Essen im Alltag?"},
            {"key": "support", "typ": "langtext",
             "frage": "Was brauchst du von mir, damit diese 4 Wochen für dich richtig gut werden?"},
            {"key": "bestaetigung", "typ": "bestaetigung",
             "frage": "Danke. Wir starten am 8. Juni – du hörst von mir."},
        ],
    ),
    "laufend": (
        "Wöchentlicher Check-in",
        [
            {"key": "wohlbefinden", "typ": "skala", "pflichtfeld": True,
             "frage": "Wie geht es dir diese Woche insgesamt?",
             "skala_min": 1, "skala_max": 10,
             "skala_labels": {"min": "schlecht", "max": "super"}},
            {"key": "energie", "typ": "skala", "pflichtfeld": True,
             "frage": "Wie war deine Energie?",
             "skala_min": 1, "skala_max": 10,
             "skala_labels": {"min": "sehr niedrig", "max": "sehr hoch"}},
            {"key": "heisshunger", "typ": "einfachauswahl", "pflichtfeld": True,
             "frage": "Heißhunger im Vergleich zu sonst?",
             "optionen": ["weniger", "gleich", "mehr"]},
            # Pro-Instanz editierbare Umsetzungsfrage. Default = Woche-1-Text;
            # Wochen 2–4 werden je Check-in-Lektion via lesson.checkin_overrides
            # überschrieben. Stabiler key 'umsetzung'.
            {"key": "umsetzung", "typ": "kurztext",
             "frage": "An wie vielen Tagen hast du blutzuckerfreundlich gefrühstückt?"},
            {"key": "win", "typ": "kurztext",
             "frage": "Dein größter Win diese Woche?"},
            {"key": "huerde", "typ": "kurztext",
             "frage": "Wo hast du gehakt?"},
            {"key": "frage", "typ": "langtext",
             "frage": "Eine Frage an mich für den nächsten Live-Call? (optional)"},
            {"key": "bestaetigung", "typ": "bestaetigung",
             "frage": "Danke für deinen Check-in – wir sehen uns im Live-Call."},
        ],
    ),
}


async def seed_checkin_templates() -> None:
    # Über das Modul auflösen (nicht beim Import binden), damit Tests die
    # gepatchte async_session/Engine treffen.
    async with db_module.async_session() as db:
        created = 0
        for typ, (name, steps) in TEMPLATES.items():
            existing = await db.execute(
                select(CheckinTemplate.id).where(CheckinTemplate.typ == typ)
            )
            if existing.scalar_one_or_none() is not None:
                continue
            template = CheckinTemplate(id=str(uuid.uuid4()), typ=typ, name=name)
            db.add(template)
            for i, step in enumerate(steps):
                db.add(CheckinStep(
                    id=str(uuid.uuid4()),
                    template_id=template.id,
                    key=step["key"],
                    typ=step["typ"],
                    frage=step.get("frage"),
                    hilfetext=step.get("hilfetext"),
                    pflichtfeld=step.get("pflichtfeld", False),
                    optionen=step.get("optionen"),
                    skala_min=step.get("skala_min"),
                    skala_max=step.get("skala_max"),
                    skala_labels=step.get("skala_labels"),
                    sort_order=i,
                ))
            created += 1
        if created:
            await db.commit()
            logger.info(f"Seeded {created} check-in template(s)")
