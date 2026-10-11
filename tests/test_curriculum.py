import copy
import tempfile
import unittest
from pathlib import Path

from sqlalchemy import func, select, text

from app import create_app
from app.curriculum_data import CURRICULUM
from app.extensions import db
from app.models import (
    Language,
    LearnerProfile,
    LearningProgress,
    Lesson,
    Topic,
    User,
)
from app.services.curriculum import CurriculumSeedError, seed_curriculum, validate_catalog


class CurriculumTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_directory.name) / "curriculum.sqlite3"
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(self.database_path),
            }
        )
        result = self.app.test_cli_runner().invoke(args=["db", "upgrade"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.engine.dispose()
        self.temp_directory.cleanup()

    def seed(self):
        result = self.app.test_cli_runner().invoke(args=["seed-curriculum"])
        self.assertEqual(
            result.exit_code,
            0,
            f"{result.output}\n{result.exception!r}",
        )
        return result.output

    def test_seed_command_loads_all_four_languages_and_ten_lessons_each(self):
        output = self.seed()

        self.assertIn("Created 4 languages, 40 topics, and 40 lessons.", output)
        with self.app.app_context():
            languages = db.session.scalars(
                select(Language).order_by(Language.position, Language.code)
            ).all()
            self.assertEqual(
                [language.code for language in languages],
                ["python", "javascript", "c", "cpp"],
            )
            for language in languages:
                self.assertEqual(len(language.topics), 10)
                self.assertEqual(
                    [topic.position for topic in language.topics],
                    list(range(10)),
                )
                self.assertEqual(sum(len(topic.lessons) for topic in language.topics), 10)
                for topic in language.topics:
                    self.assertTrue(topic.slug)
                    self.assertTrue(topic.title)
                    self.assertTrue(topic.description)
                    self.assertIn(
                        topic.difficulty,
                        {"beginner", "intermediate", "advanced"},
                    )
                    self.assertEqual(len(topic.lessons), 1)
                    self.assertTrue(topic.lessons[0].content)

    def test_repeated_seed_is_idempotent(self):
        first_output = self.seed()
        second_output = self.seed()

        self.assertIn("Created 4 languages, 40 topics, and 40 lessons.", first_output)
        self.assertIn("Created 0 languages, 0 topics, and 0 lessons.", second_output)
        with self.app.app_context():
            self.assertEqual(db.session.query(Language).count(), 4)
            self.assertEqual(db.session.query(Topic).count(), 40)
            self.assertEqual(db.session.query(Lesson).count(), 40)
            self.assertEqual(
                db.session.scalar(select(func.count()).select_from(db.metadata.tables["lesson_prerequisites"])),
                36,
            )

    def test_seed_conflict_rolls_back_partial_catalog_insert(self):
        with self.app.app_context():
            db.session.add(
                Language(
                    code="javascript",
                    name="Custom JavaScript",
                    description="A separately managed language.",
                    position=1,
                )
            )
            db.session.commit()

            with self.assertRaises(CurriculumSeedError):
                seed_curriculum()
            db.session.rollback()

            self.assertIsNone(db.session.get(Language, "python"))
            self.assertEqual(db.session.query(Topic).count(), 0)
            self.assertEqual(db.session.query(Lesson).count(), 0)
            self.assertEqual(
                db.session.get(Language, "javascript").name,
                "Custom JavaScript",
            )

    def test_seed_command_reports_failure_on_existing_content_conflict(self):
        with self.app.app_context():
            db.session.add(
                Language(
                    code="javascript",
                    name="Custom JavaScript",
                    description="A separately managed language.",
                    position=1,
                )
            )
            db.session.commit()

        result = self.app.test_cli_runner().invoke(args=["seed-curriculum"])

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("differs from the starter catalog", result.output)
        with self.app.app_context():
            self.assertIsNone(db.session.get(Language, "python"))
            self.assertEqual(db.session.query(Topic).count(), 0)

    def test_invalid_and_circular_prerequisites_are_rejected(self):
        missing_reference = list(copy.deepcopy(CURRICULUM))
        language = dict(missing_reference[0])
        topics = list(language["topics"])
        topics[1] = (
            *topics[1][:7],
            ("missing-topic", "missing-topic"),
        )
        language["topics"] = tuple(topics)
        missing_reference[0] = language
        with self.assertRaisesRegex(CurriculumSeedError, "missing prerequisite"):
            validate_catalog(missing_reference)

        circular_reference = list(copy.deepcopy(CURRICULUM))
        language = dict(circular_reference[0])
        topics = list(language["topics"])
        topics[0] = (
            *topics[0][:7],
            ("problem-solving", "problem-solving"),
        )
        language["topics"] = tuple(topics)
        circular_reference[0] = language
        with self.assertRaisesRegex(CurriculumSeedError, "Circular lesson prerequisite"):
            validate_catalog(circular_reference)

    def test_language_list_and_detail_endpoints_are_ordered_json(self):
        self.seed()

        response = self.client.get("/api/languages")
        self.assertEqual(response.status_code, 200)
        languages = response.get_json()["languages"]
        self.assertEqual(
            [language["slug"] for language in languages],
            ["python", "javascript", "c", "cpp"],
        )
        self.assertEqual(languages[0]["name"], "Python")

        response = self.client.get("/api/languages/python")
        self.assertEqual(response.status_code, 200)
        language = response.get_json()["language"]
        self.assertEqual(language["slug"], "python")
        self.assertEqual(
            [topic["position"] for topic in language["topics"]],
            list(range(10)),
        )
        self.assertEqual(language["topics"][0]["slug"], "getting-started")

    def test_topic_endpoint_returns_ordered_lessons_and_prerequisites(self):
        self.seed()
        with self.app.app_context():
            topic = db.session.scalar(
                select(Topic).where(
                    Topic.language_code == "python",
                    Topic.slug == "variables-and-types",
                )
            )
            db.session.add(
                Lesson(
                    topic=topic,
                    slug="extra-practice",
                    title="Extra practice",
                    description="An additional ordered lesson for the test.",
                    content="A test fixture lesson.",
                    position=1,
                )
            )
            db.session.commit()

        response = self.client.get(
            "/api/languages/python/topics/variables-and-types"
        )
        self.assertEqual(response.status_code, 200)
        topic = response.get_json()["topic"]
        self.assertEqual(topic["slug"], "variables-and-types")
        self.assertEqual(
            [lesson["slug"] for lesson in topic["lessons"]],
            ["variables-and-types", "extra-practice"],
        )
        self.assertEqual(
            topic["lessons"][0]["prerequisites"],
            [{"topic_slug": "first-output", "lesson_slug": "first-output"}],
        )

        lesson_response = self.client.get(
            "/api/languages/python/topics/variables-and-types/"
            "lessons/variables-and-types"
        )
        self.assertEqual(lesson_response.status_code, 200)
        lesson = lesson_response.get_json()["lesson"]
        self.assertEqual(lesson["language_slug"], "python")
        self.assertEqual(lesson["topic_slug"], "variables-and-types")

    def test_unknown_language_topic_and_lesson_return_json_404(self):
        self.seed()

        paths = (
            "/api/languages/rust",
            "/api/languages/python/topics/not-a-topic",
            "/api/languages/python/topics/first-output/lessons/not-a-lesson",
            "/api/languages/not-a-language/topics/first-output",
        )
        for path in paths:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 404)
                self.assertEqual(
                    response.get_json()["error"]["code"],
                    "not_found",
                )

    def test_reseeding_preserves_user_profile_and_learning_progress(self):
        self.seed()
        with self.app.app_context():
            user = User()
            profile = LearnerProfile(user=user, display_name="Sample")
            lesson = db.session.scalar(
                select(Lesson).join(Lesson.topic).where(
                    Topic.language_code == "python",
                    Topic.slug == "first-output",
                )
            )
            progress = LearningProgress(user=user, lesson=lesson)
            db.session.add_all([user, profile, progress])
            db.session.commit()
            user_id = user.id
            lesson_id = lesson.id

            counts = seed_curriculum()
            self.assertEqual(counts, {"languages": 0, "topics": 0, "lessons": 0})
            self.assertIsNotNone(db.session.get(User, user_id))
            self.assertEqual(
                db.session.get(LearnerProfile, user_id).display_name,
                "Sample",
            )
            self.assertEqual(
                db.session.get(LearningProgress, (user_id, lesson_id)).status,
                "not_started",
            )

    def test_migrations_apply_and_schema_has_no_drift(self):
        result = self.app.test_cli_runner().invoke(args=["db", "current"])
        self.assertEqual(result.exit_code, 0, result.output)
        with self.app.app_context():
            revision = db.session.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
        self.assertEqual(revision, "a81f2d7c9b44")

        result = self.app.test_cli_runner().invoke(args=["db", "check"])
        self.assertEqual(result.exit_code, 0, result.output)


if __name__ == "__main__":
    unittest.main()
