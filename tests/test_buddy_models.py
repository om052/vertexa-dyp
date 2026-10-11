import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError

from app import create_app
from app.extensions import db
from app.models import (
    BuddyConversation,
    BuddyMemoryItem,
    BuddyMessage,
    BuddyPrivacySettings,
    Language,
    LearnerProfile,
    LearningProgress,
    Lesson,
    Topic,
    User,
    utc_now,
)


class BuddyModelTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_directory.name) / "buddy.sqlite3"
        self.app = self.make_app(self.database_path)
        result = self.app.test_cli_runner().invoke(args=["db", "upgrade"])
        self.assertEqual(result.exit_code, 0, result.output)

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

    def create_conversation(self, user):
        now = utc_now()
        conversation = BuddyConversation(
            user=user,
            history_consent_at=now,
            history_policy_version="v1",
            created_at=now,
            updated_at=now,
            last_meaningful_at=now,
            expires_at=now + timedelta(days=90),
        )
        db.session.add(conversation)
        db.session.flush()
        return conversation

    def test_buddy_models_create_and_relationships_round_trip(self):
        with self.app.app_context():
            user = User()
            db.session.add(user)
            conversation = self.create_conversation(user)
            message = BuddyMessage(
                conversation=conversation,
                role="user",
                sequence=0,
                content="Please explain this loop.",
            )
            memory = BuddyMemoryItem(
                user=user,
                category="explanation_preference",
                content="Short examples are helpful.",
                learner_approved_at=utc_now(),
            )
            settings = BuddyPrivacySettings(
                user=user,
                memory_enabled=True,
                memory_consent_at=utc_now(),
                memory_policy_version="v1",
            )
            db.session.add_all([message, memory, settings])
            db.session.commit()

            loaded_user = db.session.get(User, user.id)
            loaded_conversation = db.session.get(BuddyConversation, conversation.id)
            self.assertEqual(loaded_conversation.user_id, loaded_user.id)
            self.assertEqual(loaded_user.buddy_conversations, [loaded_conversation])
            self.assertEqual(loaded_conversation.messages[0].role, "user")
            self.assertEqual(loaded_user.buddy_memory_items[0].id, memory.id)
            self.assertTrue(loaded_user.buddy_memory_enabled)
            self.assertEqual(
                loaded_conversation.expires_at - loaded_conversation.last_meaningful_at,
                timedelta(days=90),
            )
            self.assertIsNotNone(loaded_conversation.created_at.tzinfo)
            self.assertIsNotNone(message.created_at.tzinfo)

    def test_conversation_requires_explicit_history_consent(self):
        with self.app.app_context():
            user = User()
            db.session.add(user)
            db.session.flush()
            now = utc_now()
            conversation = BuddyConversation(
                user=user,
                history_policy_version="v1",
                created_at=now,
                updated_at=now,
                last_meaningful_at=now,
                expires_at=now + timedelta(days=90),
            )
            db.session.add(conversation)
            with self.assertRaises(IntegrityError):
                db.session.commit()
            db.session.rollback()

    def test_message_role_content_and_sequence_constraints(self):
        with self.app.app_context():
            user = User()
            db.session.add(user)
            conversation = self.create_conversation(user)
            db.session.add(
                BuddyMessage(
                    conversation=conversation,
                    role="system",
                    sequence=0,
                    content="Invalid role.",
                )
            )
            with self.assertRaises(IntegrityError):
                db.session.commit()
            db.session.rollback()

            conversation = db.session.get(BuddyConversation, conversation.id)
            db.session.add_all(
                [
                    BuddyMessage(
                        conversation=conversation,
                        role="user",
                        sequence=0,
                        content="First message.",
                    ),
                    BuddyMessage(
                        conversation=conversation,
                        role="assistant",
                        sequence=0,
                        content="Duplicate sequence.",
                    ),
                ]
            )
            with self.assertRaises(IntegrityError):
                db.session.commit()
            db.session.rollback()

            db.session.add(
                BuddyMessage(
                    conversation=conversation,
                    role="assistant",
                    sequence=0,
                    content=" " * 3,
                )
            )
            with self.assertRaises(IntegrityError):
                db.session.commit()
            db.session.rollback()

    def test_memory_requires_approval_valid_category_and_bounded_content(self):
        with self.app.app_context():
            user = User()
            db.session.add(user)
            memory = BuddyMemoryItem(
                user=user,
                category="learning_goal",
                content="Learn Python.",
            )
            db.session.add(memory)
            with self.assertRaises(IntegrityError):
                db.session.commit()
            db.session.rollback()

            db.session.add(
                BuddyMemoryItem(
                    user=user,
                    category="private_secret",
                    content="Not an allowed category.",
                    learner_approved_at=utc_now(),
                )
            )
            with self.assertRaises(IntegrityError):
                db.session.commit()
            db.session.rollback()

            db.session.add(
                BuddyMemoryItem(
                    user=user,
                    category="learning_goal",
                    content="x" * 501,
                    learner_approved_at=utc_now(),
                )
            )
            with self.assertRaises(IntegrityError):
                db.session.commit()
            db.session.rollback()

    def test_memory_is_disabled_when_settings_are_absent_or_defaulted(self):
        with self.app.app_context():
            user = User()
            db.session.add(user)
            db.session.commit()
            user_id = user.id

            loaded_user = db.session.get(User, user_id)
            self.assertIsNone(loaded_user.buddy_privacy_settings)
            self.assertFalse(loaded_user.buddy_memory_enabled)

            settings = BuddyPrivacySettings(user=loaded_user)
            db.session.add(settings)
            db.session.commit()
            db.session.refresh(settings)
            self.assertFalse(settings.memory_enabled)
            self.assertIsNone(settings.memory_consent_at)
            self.assertIsNone(settings.memory_policy_version)
            self.assertFalse(loaded_user.buddy_memory_enabled)

    def test_enabled_memory_requires_consent_timestamp_and_policy_version(self):
        with self.app.app_context():
            user = User()
            db.session.add(user)
            db.session.add(
                BuddyPrivacySettings(
                    user=user,
                    memory_enabled=True,
                    memory_policy_version="v1",
                )
            )
            with self.assertRaises(IntegrityError):
                db.session.commit()
            db.session.rollback()

    def test_conversation_deletion_cascades_to_messages(self):
        with self.app.app_context():
            user = User()
            db.session.add(user)
            conversation = self.create_conversation(user)
            message = BuddyMessage(
                conversation=conversation,
                role="assistant",
                sequence=0,
                content="A hint.",
            )
            db.session.add(message)
            db.session.commit()
            conversation_id = conversation.id
            message_id = message.id

            db.session.delete(conversation)
            db.session.commit()
            self.assertIsNone(db.session.get(BuddyConversation, conversation_id))
            self.assertIsNone(db.session.get(BuddyMessage, message_id))

    def test_user_deletion_cascades_only_buddy_owned_rows(self):
        with self.app.app_context():
            language = Language(code="python", name="Python")
            topic = Topic(
                language=language,
                slug="loops",
                title="Loops",
            )
            lesson = Lesson(
                topic=topic,
                slug="first-loop",
                title="First loop",
                content="Example lesson.",
                position=0,
            )
            user = User()
            db.session.add_all([language, topic, lesson, user])
            db.session.flush()
            user_id = user.id
            conversation = self.create_conversation(user)
            conversation_id = conversation.id
            db.session.add(
                BuddyMessage(
                    conversation=conversation,
                    role="user",
                    sequence=0,
                    content="Question.",
                )
            )
            memory = BuddyMemoryItem(
                user=user,
                category="learning_focus",
                content="Loops.",
                learner_approved_at=utc_now(),
            )
            settings = BuddyPrivacySettings(user=user)
            progress = LearningProgress(user=user, lesson=lesson)
            db.session.add_all([memory, settings, progress])
            db.session.commit()
            memory_id = memory.id
            lesson_id = lesson.id

            db.session.delete(user)
            db.session.commit()
            self.assertIsNone(db.session.get(BuddyConversation, conversation_id))
            self.assertIsNone(
                db.session.scalar(
                    select(BuddyMessage).where(
                        BuddyMessage.conversation_id == conversation_id
                    )
                )
            )
            self.assertIsNone(db.session.get(BuddyMemoryItem, memory_id))
            self.assertIsNone(db.session.get(BuddyPrivacySettings, user_id))
            self.assertIsNone(db.session.get(LearningProgress, (user_id, lesson_id)))
            self.assertIsNotNone(db.session.get(Language, "python"))
            self.assertIsNotNone(db.session.get(Lesson, lesson_id))

    def test_additive_migration_preserves_existing_learner_data(self):
        migration_directory = tempfile.TemporaryDirectory()
        migration_path = Path(migration_directory.name) / "migration.sqlite3"
        migration_app = self.make_app(migration_path)
        try:
            parent_upgrade = migration_app.test_cli_runner().invoke(
                args=["db", "upgrade", "a81f2d7c9b44"]
            )
            self.assertEqual(parent_upgrade.exit_code, 0, parent_upgrade.output)

            with migration_app.app_context():
                user = User(username="existing_learner", email="existing@example.com")
                profile = LearnerProfile(user=user, display_name="Existing")
                language = Language(code="python", name="Python")
                topic = Topic(language=language, slug="loops", title="Loops")
                lesson = Lesson(
                    topic=topic,
                    slug="first-loop",
                    title="First loop",
                    content="Existing lesson.",
                    position=0,
                )
                progress = LearningProgress(user=user, lesson=lesson)
                db.session.add_all([user, profile, language, topic, lesson, progress])
                db.session.commit()
                user_id = user.id
                lesson_id = lesson.id

            buddy_upgrade = migration_app.test_cli_runner().invoke(
                args=["db", "upgrade"]
            )
            self.assertEqual(buddy_upgrade.exit_code, 0, buddy_upgrade.output)

            with migration_app.app_context():
                revision = db.session.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar_one()
                self.assertEqual(revision, "b7c4e91a6d20")
                self.assertIsNotNone(db.session.get(User, user_id))
                self.assertEqual(
                    db.session.get(LearnerProfile, user_id).display_name,
                    "Existing",
                )
                self.assertIsNotNone(db.session.get(Lesson, lesson_id))
                self.assertEqual(
                    db.session.get(LearningProgress, (user_id, lesson_id)).status,
                    "not_started",
                )
                table_names = set(inspect(db.engine).get_table_names())
                self.assertTrue(
                    {
                        "buddy_conversations",
                        "buddy_messages",
                        "buddy_memory_items",
                        "buddy_privacy_settings",
                    }.issubset(table_names)
                )
        finally:
            with migration_app.app_context():
                db.session.remove()
                db.engine.dispose()
            migration_directory.cleanup()


if __name__ == "__main__":
    unittest.main()
