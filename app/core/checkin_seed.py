"""Seed der drei Check-In-Templates (start, laufend, ende).

Idempotent: legt ein Template nur an, wenn für seinen `typ` noch keines existiert.
Re-Runs sind ein No-op und überschreiben NICHT, was Nora im Admin editiert hat.
Die Texte/Optionen leben damit in der DB (editierbar), nicht hartkodiert im Player.
"""
import logging
import uuid

from sqlalchemy import select

from app.core import db as db_module
from app.models.checkin import CheckinTemplate, CheckinStep, CheckinResponse

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
            # Eigener Key (NICHT 'heisshunger'): start/ende fragen Heißhunger
            # absolut ab (täglich…nie, key 'heisshunger'), laufend fragt RELATIV
            # (weniger/gleich/mehr). Unterschiedliche Semantik -> eindeutiger Key,
            # sonst kollidieren die Werte in template-übergreifenden Auswertungen.
            {"key": "heisshunger_trend", "typ": "einfachauswahl", "pflichtfeld": True,
             "frage": "Heißhunger im Vergleich zu sonst?",
             "optionen": ["weniger", "gleich", "mehr"]},
            # Pro-Instanz editierbare Umsetzungsfrage. Default = Woche-1-Text;
            # Wochen 2–4 werden je Check-in-Lektion via lesson.checkin_overrides
            # überschrieben. Stabiler key 'umsetzung'.
            {"key": "umsetzung", "typ": "kurztext",
             "frage": "An wie vielen Tagen hast du blutzuckerfreundlich gefrühstückt?"},
            {"key": "win", "typ": "kurztext",
             "frage": "Dein größter Erfolg diese Woche?"},
            {"key": "huerde", "typ": "kurztext",
             "frage": "Wo hat es nicht geklappt?"},
            {"key": "frage", "typ": "langtext",
             "frage": "Eine Frage an mich für den nächsten Live-Call? (optional)"},
            {"key": "bestaetigung", "typ": "bestaetigung",
             "frage": "Danke für deinen Check-in – wir sehen uns im Live-Call."},
        ],
    ),
    "ende": (
        "Abschluss-Check-in",
        [
            {"key": "intro", "typ": "intro",
             "frage": "Vier Wochen geschafft. Nimm dir 3 Minuten, um zurückzuschauen – und nach vorn."},
            {"key": "rueckblick", "typ": "langtext",
             "frage": "Was hat sich in diesen 4 Wochen für dich verändert? Was ist heute besser als am Anfang?"},
            # Gespiegelte Skalen/Auswahlen mit denselben keys wie im Start-Template
            # (energie, nachmittagstief, heisshunger) -> CRM kann start vs. ende
            # pro key direkt vergleichen (Vorher/Nachher). Optionen/Skala müssen
            # identisch zum Start bleiben, sonst bricht der Vergleich.
            {"key": "energie", "typ": "skala", "pflichtfeld": True,
             "frage": "Wie ist deine Energie im Alltag jetzt?",
             "skala_min": 1, "skala_max": 10,
             "skala_labels": {"min": "sehr niedrig", "max": "sehr hoch"}},
            {"key": "nachmittagstief", "typ": "einfachauswahl", "pflichtfeld": True,
             "frage": "Wie oft erwischt dich jetzt ein Nachmittags- oder Energietief?",
             "optionen": _HAEUFIGKEIT},
            {"key": "heisshunger", "typ": "einfachauswahl", "pflichtfeld": True,
             "frage": "Wie oft hast du jetzt Heißhunger?",
             "optionen": _HAEUFIGKEIT},
            {"key": "takeaways", "typ": "langtext",
             "frage": "Was sind deine wichtigsten Take-aways aus dem Programm?"},
            {"key": "anker", "typ": "langtext",
             "frage": "Welche Anker und Gewohnheiten willst du unbedingt beibehalten?"},
            {"key": "naechster_schritt", "typ": "langtext",
             "frage": "Was nimmst du dir als Nächstes vor – für die Zeit nach diesen 4 Wochen?"},
            {"key": "dranbleiben", "typ": "langtext",
             "frage": "Wie stellst du sicher, dass du dranbleibst?"},
            {"key": "premium_interesse", "typ": "einfachauswahl",
             "frage": "Magst du den Weg in der Gruppe weitergehen? Im Premium-Coaching begleite ich dich gemeinsam mit anderen Frauen weiter.",
             "optionen": ["Ja, erzähl mir mehr", "Vielleicht später", "Für mich erstmal nicht"]},
            {"key": "bestaetigung", "typ": "bestaetigung",
             "frage": "Ich bin richtig stolz auf dich. Vier Wochen dranbleiben – das schaffen die wenigsten. Wenn du magst, gehen wir den nächsten Schritt gemeinsam: Ich melde mich bei dir."},
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


# Einmalige, idempotente Korrekturen an Default-Fragetexten BEREITS geseedeter
# Templates. Der normale Seeder fasst existierende Templates nicht an; diese
# Liste hebt nur Default-Texte an, die Nora ohnehin bei jedem Formular von Hand
# umformuliert hat. Greift nur, solange der Step noch den ALTEN Default trägt.
# Risikofrei: Template-Steps werden nie im Admin editiert (Admin schreibt nur
# lesson-Overrides), und sobald der neue Text steht, ist ein Re-Run ein No-op.
# (typ, key, alter Default, neuer Default)
_DEFAULT_TEXT_FIXES: list[tuple[str, str, str, str]] = [
    ("laufend", "win", "Dein größter Win diese Woche?", "Dein größter Erfolg diese Woche?"),
    ("laufend", "huerde", "Wo hast du gehakt?", "Wo hat es nicht geklappt?"),
]


async def sync_checkin_default_texts() -> None:
    """Hebt veraltete Default-Fragetexte in der Live-DB an (siehe _DEFAULT_TEXT_FIXES)."""
    async with db_module.async_session() as db:
        updated = 0
        for typ, key, old, new in _DEFAULT_TEXT_FIXES:
            result = await db.execute(
                select(CheckinStep)
                .join(CheckinTemplate, CheckinStep.template_id == CheckinTemplate.id)
                .where(
                    CheckinTemplate.typ == typ,
                    CheckinStep.key == key,
                    CheckinStep.frage == old,
                )
            )
            for step in result.scalars():
                step.frage = new
                updated += 1
        if updated:
            await db.commit()
            logger.info(f"Updated {updated} check-in default text(s)")


# Eindeutige Umbenennung mehrdeutiger 'laufend'-Step-Keys. Hintergrund: 'start'
# und 'ende' fragen Heißhunger ABSOLUT ab (täglich…nie, key 'heisshunger'),
# 'laufend' fragte denselben Key RELATIV (weniger/gleich/mehr). Gleicher Key,
# zwei Vokabulare -> Kollision in template-übergreifenden Auswertungen. Wir
# benennen den laufend-Key um und ziehen Template-Step, historische Antworten und
# Lesson-Overrides mit. (alter Key, neuer Key)
_LAUFEND_KEY_RENAMES: list[tuple[str, str]] = [
    ("heisshunger", "heisshunger_trend"),
]


async def migrate_laufend_step_keys() -> None:
    """Benennt mehrdeutige 'laufend'-Step-Keys eindeutig um. Migriert Template-
    Step, historische CheckinResponse.answers und Lesson-Overrides mit. Fasst nur
    den jeweils ALTEN Key an -> idempotent, Re-Run = No-op."""
    from app.models.course import Lesson  # lazy: vermeidet Import-Zyklus

    async with db_module.async_session() as db:
        tmpl_ids = (await db.execute(
            select(CheckinTemplate.id).where(CheckinTemplate.typ == "laufend")
        )).scalars().all()
        if not tmpl_ids:
            return

        changed = 0
        for old, new in _LAUFEND_KEY_RENAMES:
            # 1. Template-Step(s)
            for step in (await db.execute(
                select(CheckinStep).where(
                    CheckinStep.template_id.in_(tmpl_ids), CheckinStep.key == old
                )
            )).scalars():
                step.key = new
                changed += 1

            # 2. Historische Antworten (nur laufend) — answers neu zuweisen, damit
            #    SQLAlchemy die JSON-Änderung erkennt.
            for resp in (await db.execute(
                select(CheckinResponse).where(CheckinResponse.template_typ == "laufend")
            )).scalars():
                if isinstance(resp.answers, dict) and old in resp.answers:
                    a = dict(resp.answers)
                    a[new] = a.pop(old)
                    resp.answers = a
                    changed += 1

            # 3. Lesson-Overrides der laufend-Lektionen (steps.<key>)
            for lesson in (await db.execute(
                select(Lesson).where(Lesson.checkin_template_id.in_(tmpl_ids))
            )).scalars():
                ov = lesson.checkin_overrides
                steps_ov = ov.get("steps") if isinstance(ov, dict) else None
                if isinstance(steps_ov, dict) and old in steps_ov:
                    new_steps = dict(steps_ov)
                    new_steps[new] = new_steps.pop(old)
                    lesson.checkin_overrides = {**ov, "steps": new_steps}
                    changed += 1

        if changed:
            await db.commit()
            logger.info(f"Renamed {changed} laufend step-key occurrence(s)")
