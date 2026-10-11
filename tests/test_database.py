import tempfile
import unittest
from pathlib import Path

from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from app import create_app
from app.extensions import db
from app.models import (
    Language,
    LearnerProfile,
    LearningProgress,
    Lesson,
    Topic,
    User,
)


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_directory.name) / "test.sqlite3"
        self.app = self.make_app(self.database_path)
        result = self.app.test_cli_runner().invoke(args=["db", "upgrade"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.engine.dispose()
        self.temp_directory.cleanup()

    @staticmethod
    def make_app(database_path):
        return create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(database_path),
            }
        )

    def add_learning_content(self):
        language = Language(code="python", name="Python")
        topic = Topic(
            language=language,
            slug="variables",
            title="Variables",
        )
        lesson = Lesson(
            topic=topic,
            slug="first-values",
            title="Your first values",
            content="Lesson content stored independently of the frontend.",
            position=0,
        )
        db.session.add_all([language, topic, lesson])
        db.session.flush()
        return language, topic, lesson

    def test_fresh_database_is_created_by_migration(self):
        self.assertTrue(self.database_path.exists())
        with self.app.app_context():
            tables = set(inspect(db.engine).get_table_names())

        self.assertTrue(
            {
                "alembic_version",
                "users",
                "learner_profiles",
                "languages",
                "topics",
                "lessons",
                "learning_progress",
            }.issubset(tables)
        )

    def test_migration_can_be_reapplied_without_losing_records(self):
        with self.app.app_context():
            user = User()
            db.session.add(user)
            db.session.commit()
            user_id = user.id

        result = self.app.test_cli_runner().invoke(args=["db", "upgrade"])
        self.assertEqual(result.exit_code, 0, result.output)

        with self.app.app_context():
            self.assertIsNotNone(db.session.get(User, user_id))

    def test_valid_user_profile_content_and_progress_round_trip(self):
        with self.app.app_context():
            language, topic, lesson = self.add_learning_content()
            user = User()
            profile = LearnerProfile(
                user=user,
                display_name="Learner",
                preferred_language=language,
            )
            progress = LearningProgress(user=user, lesson=lesson)
            db.session.add_all([user, profile, progress])
            db.session.commit()
            user_id = user.id
            lesson_id = lesson.id
            created_at = user.created_at

            loaded_user = db.session.get(User, user_id)
            loaded_profile = db.session.get(LearnerProfile, user_id)
            loaded_progress = db.session.get(
                LearningProgress, (user_id, lesson_id)
            )

            self.assertIsNotNone(loaded_user)
            self.assertEqual(loaded_user.id, user_id)
            self.assertIsNotNone(loaded_user.created_at.tzinfo)
            self.assertIsNotNone(created_at.tzinfo)
            self.assertEqual(loaded_profile.display_name, "Learner")
            self.assertEqual(loaded_profile.preferred_language_code, "python")
            self.assertEqual(loaded_progress.status, "not_started")
            self.assertEqual(loaded_user.id, profile.user_id)
            self.assertEqual(lesson.topic_id, topic.id)

    def test_unique_language_and_topic_constraints_are_enforced(self):
        with self.app.app_context():
            db.session.add_all(
                [
                    Language(code="python", name="Python"),
                    Language(code="python", name="Python 3"),
                ]
            )
            with self.assertRaises(IntegrityError):
                db.session.commit()
            db.session.rollback()

            language, _, _ = self.add_learning_content()
            db.session.add(
                Topic(
                    language=language,
                    slug="variables",
                    title="Duplicate topic",
                )
            )
            with self.assertRaises(IntegrityError):
                db.session.commit()
            db.session.rollback()

    def test_foreign_key_integrity_is_enabled_and_enforced(self):
        with self.app.app_context():
            with db.engine.connect() as connection:
                enabled = connection.execute(
                    text("PRAGMA foreign_keys")
                ).scalar_one()
            self.assertEqual(enabled, 1)

            db.session.add(
                Topic(
                    language_code="missing-language",
                    slug="topic",
                    title="Topic",
                )
            )
            with self.assertRaises(IntegrityError):
                db.session.commit()
            db.session.rollback()

    def test_invalid_required_fields_and_progress_status_are_rejected(self):
        with self.app.app_context():
            db.session.add(Language(code="", name=""))
            with self.assertRaises(IntegrityError):
                db.session.commit()
            db.session.rollback()

            _, _, lesson = self.add_learning_content()
            user = User()
            db.session.add(
                LearningProgress(
                    user=user,
                    lesson=lesson,
                    status="mastered",
                )
            )
            with self.assertRaises(IntegrityError):
                db.session.commit()
            db.session.rollback()

    def test_reopening_database_preserves_records(self):
        with self.app.app_context():
            user = User()
            db.session.add(user)
            db.session.commit()
            user_id = user.id
            db.session.remove()
            db.engine.dispose()

        reopened_app = self.make_app(self.database_path)
        with reopened_app.app_context():
            reopened_user = db.session.get(User, user_id)
            self.assertIsNotNone(reopened_user)
            self.assertEqual(reopened_user.id, user_id)
            db.session.remove()
            db.engine.dispose()

    def test_databases_are_isolated(self):
        second_path = Path(self.temp_directory.name) / "second.sqlite3"
        second_app = self.make_app(second_path)
        result = second_app.test_cli_runner().invoke(args=["db", "upgrade"])
        self.assertEqual(result.exit_code, 0, result.output)

        with self.app.app_context():
            user = User()
            db.session.add(user)
            db.session.commit()
            user_id = user.id

        with second_app.app_context():
            self.assertIsNone(db.session.get(User, user_id))
            db.session.remove()
            db.engine.dispose()

    def test_homepage_and_health_endpoint_remain_available(self):
        self.assertEqual(self.client.get("/").status_code, 200)
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"status": "ok"})

    def test_language_cannot_be_deleted_while_topics_reference_it(self):
        with self.app.app_context():
            language, _, _ = self.add_learning_content()
            db.session.delete(language)
            with self.assertRaises(IntegrityError):
                db.session.commit()
            db.session.rollback()


if __name__ == "__main__":
    unittest.main()
