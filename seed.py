"""Seed script: Creates an admin user and a demo course structure."""
import asyncio
from app.core.db import engine, Base, async_session
from app.core.auth import hash_password
from app.models.user import User
from app.models.course import Course, Module, Section, Lesson, Enrollment


async def seed():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as db:
        # Admin user
        admin = User(
            id="admin-1",
            email="nora@noraweweler.de",
            name="Nora Weweler",
            hashed_password=hash_password("admin123"),
            is_admin=True,
        )
        db.add(admin)

        # Demo student
        student = User(
            id="student-1",
            email="test@example.com",
            name="Test Teilnehmer",
            hashed_password=hash_password("test123"),
            is_admin=False,
        )
        db.add(student)

        # Course: Vibe-Coden
        course = Course(
            id="course-1",
            title="Vibe-Coden",
            description="Lerne, wie du mit KI-Tools deine eigenen Apps und Websites baust - ohne Programmierkenntnisse.",
            is_active=True,
            sort_order=0,
        )
        db.add(course)

        # Module 1
        mod1 = Module(
            id="mod-1", course_id="course-1",
            title="Modul 1 | Einfuhrung ins Vibe-Coden",
            description="Was ist Vibe-Coden und warum ist es der Game-Changer?",
            sort_order=0,
        )
        db.add(mod1)

        sec1 = Section(id="sec-1", module_id="mod-1", title="Willkommen", sort_order=0)
        db.add(sec1)

        db.add(Lesson(id="les-1", section_id="sec-1", title="Willkommen zum Kurs Vibe-Coden", duration_minutes=3, sort_order=0, video_url="https://www.youtube.com/embed/dQw4w9WgXcQ"))
        db.add(Lesson(id="les-2", section_id="sec-1", title="Was du in diesem Kurs lernst", duration_minutes=5, sort_order=1))
        db.add(Lesson(id="les-3", section_id="sec-1", title="Dein Setup vorbereiten", duration_minutes=8, sort_order=2))

        sec2 = Section(id="sec-2", module_id="mod-1", title="Grundlagen", sort_order=1)
        db.add(sec2)

        db.add(Lesson(id="les-4", section_id="sec-2", title="Was ist ein Prompt?", duration_minutes=6, sort_order=0))
        db.add(Lesson(id="les-5", section_id="sec-2", title="Dein erster KI-Chat", duration_minutes=10, sort_order=1))

        # Module 2
        mod2 = Module(
            id="mod-2", course_id="course-1",
            title="Modul 2 | Deine erste Website",
            description="In diesem Modul baust du deine erste komplette Website mit KI.",
            sort_order=1,
        )
        db.add(mod2)

        sec3 = Section(id="sec-3", module_id="mod-2", title="Website Basics", sort_order=0)
        db.add(sec3)

        db.add(Lesson(id="les-6", section_id="sec-3", title="HTML & CSS verstehen (ohne coden)", duration_minutes=7, sort_order=0))
        db.add(Lesson(id="les-7", section_id="sec-3", title="Deine Landing Page mit Claude", duration_minutes=15, sort_order=1))
        db.add(Lesson(id="les-8", section_id="sec-3", title="Design anpassen und live stellen", duration_minutes=12, sort_order=2))

        # Module 3
        mod3 = Module(
            id="mod-3", course_id="course-1",
            title="Modul 3 | Apps bauen mit KI",
            description="Jetzt wird es ernst - du baust deine erste richtige App.",
            sort_order=2,
        )
        db.add(mod3)

        sec4 = Section(id="sec-4", module_id="mod-3", title="App-Entwicklung", sort_order=0)
        db.add(sec4)

        db.add(Lesson(id="les-9", section_id="sec-4", title="Was ist eine Web-App?", duration_minutes=5, sort_order=0))
        db.add(Lesson(id="les-10", section_id="sec-4", title="Datenbank & Backend verstehen", duration_minutes=10, sort_order=1))
        db.add(Lesson(id="les-11", section_id="sec-4", title="Deine Todo-App mit Cursor", duration_minutes=20, sort_order=2))
        db.add(Lesson(id="les-12", section_id="sec-4", title="Deployment: Deine App online stellen", duration_minutes=8, sort_order=3))

        # Enrollments
        db.add(Enrollment(id="enr-1", user_id="admin-1", course_id="course-1"))
        db.add(Enrollment(id="enr-2", user_id="student-1", course_id="course-1"))

        await db.commit()
        print("Seed complete!")
        print("  Admin: nora@noraweweler.de / admin123")
        print("  Student: test@example.com / test123")


if __name__ == "__main__":
    asyncio.run(seed())
