import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import func, select
from app import create_app
from app.extensions import db
from app.models import BuddyConversation, BuddyMemoryItem, BuddyMessage, User, utc_now
from app.services.buddy_common import (
    BuddyResourceNotFound,
    ConfirmationRequired,
    ConsentRequired,
    InvalidBuddyInput,
    LearnerApprovalRequired,
    MemoryDisabled,
)
from app.services.buddy_conversations import (
    append_message,
    create_saved_conversation,
    delete_all_saved_conversations,
    delete_saved_conversation,
    get_saved_conversation,
    get_saved_messages,
    list_saved_conversations,
)
from app.services.buddy_memory import (
    create_memory_item,
    delete_memory_item,
    edit_memory_item,
    get_memory_item,
    is_memory_enabled,
    list_memory_items,
    set_memory_enabled,
)
from app.services.buddy_retention import purge_expired_conversations


class BuddyServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_directory.name) / "buddy-services.sqlite3"
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(self.database_path),
            }
        )
        result = self.app.test_cli_runner().invoke(args=["db", "upgrade"])
        self.assertEqual(result.exit_code, 0, result.output)
        with self.app.app_context():
            self.user_ids = [self.create_user(), self.create_user()]

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.engine.dispose()
        self.temp_directory.cleanup()

    @staticmethod
    def create_user():
        user = User()
        db.session.add(user)
        db.session.commit()
        return user.id

    def create_conversation(self, user_id, *, now=None):
        return create_saved_conversation(
            user_id,
            history_consent=True,
            policy_version="history-v1",
            now=now,
        )

    def enable_memory(self, user_id, *, now=None):
        return set_memory_enabled(
            user_id,
            enabled=True,
            policy_version="memory-v1",
            now=now,
        )

    def create_memory(self, user_id, content="Learn Python loops."):
        return create_memory_item(
            user_id,
            category="learning_goal",
            content=content,
            learner_approved=True,
        )

    def test_missing_history_consent_is_rejected_without_persisting(self):
        with self.app.app_context():
            with self.assertRaises(ConsentRequired):
                create_saved_conversation(
                    self.user_ids[0],
                    history_consent=False,
                    policy_version="history-v1",
                )
            self.assertEqual(
                db.session.scalar(
                    select(func.count()).select_from(BuddyConversation)
                ),
                0,
            )
            with self.assertRaises(InvalidBuddyInput):
                create_saved_conversation(
                    self.user_ids[0],
                    history_consent=True,
                    policy_version=" ",
                )

    def test_valid_consent_creates_saved_conversation_and_default_expiry(self):
        now = utc_now()
        with self.app.app_context():
            conversation = self.create_conversation(self.user_ids[0], now=now)
            self.assertEqual(conversation.history_consent_at, now)
            self.assertEqual(conversation.history_policy_version, "history-v1")
            self.assertEqual(conversation.last_meaningful_at, now)
            self.assertEqual(conversation.expires_at, now + timedelta(days=90))

    def test_messages_are_appended_and_retrieved_in_sequence(self):
        now = utc_now()
        with self.app.app_context():
            conversation = self.create_conversation(self.user_ids[0], now=now)
            user_message = append_message(
                self.user_ids[0],
                conversation.id,
                role="user",
                content="  I am stuck.  ",
                now=now + timedelta(days=2),
            )
            assistant_message = append_message(
                self.user_ids[0],
                conversation.id,
                role="assistant",
                content="Try tracing the loop condition.",
                now=now + timedelta(days=2, seconds=1),
            )
            messages = get_saved_messages(self.user_ids[0], conversation.id)
            self.assertEqual(
                [(item.sequence, item.role) for item in messages],
                [(0, "user"), (1, "assistant")],
            )
            self.assertEqual(user_message.content, "I am stuck.")
            self.assertEqual(assistant_message.sequence, 1)
            refreshed = get_saved_conversation(self.user_ids[0], conversation.id)
            self.assertEqual(
                refreshed.last_meaningful_at,
                now + timedelta(days=2),
            )
            self.assertEqual(
                refreshed.expires_at,
                now + timedelta(days=92),
            )

    def test_unowned_conversation_cannot_be_read_appended_or_deleted(self):
        with self.app.app_context():
            conversation = self.create_conversation(self.user_ids[0])
            with self.assertRaises(BuddyResourceNotFound):
                get_saved_conversation(self.user_ids[1], conversation.id)
            with self.assertRaises(BuddyResourceNotFound):
                get_saved_messages(self.user_ids[1], conversation.id)
            with self.assertRaises(BuddyResourceNotFound):
                append_message(
                    self.user_ids[1],
                    conversation.id,
                    role="user",
                    content="Unauthorized",
                )
            with self.assertRaises(BuddyResourceNotFound):
                delete_saved_conversation(self.user_ids[1], conversation.id)
            self.assertIsNotNone(
                db.session.get(BuddyConversation, conversation.id)
            )

    def test_listing_excludes_conversation_at_exact_expiry_boundary(self):
        now = utc_now()
        with self.app.app_context():
            active = self.create_conversation(self.user_ids[0], now=now)
            expired = self.create_conversation(
                self.user_ids[0],
                now=now - timedelta(days=90),
            )
            other_user = self.create_conversation(self.user_ids[1], now=now)
            listed = list_saved_conversations(self.user_ids[0], now=now)
            self.assertEqual([item.id for item in listed], [active.id])
            with self.assertRaises(BuddyResourceNotFound):
                get_saved_conversation(
                    self.user_ids[0],
                    expired.id,
                    now=expired.expires_at,
                )
            self.assertNotIn(other_user.id, {item.id for item in listed})

    def test_purge_removes_expired_and_cascades_but_preserves_other_data(self):
        now = utc_now()
        with self.app.app_context():
            expired = self.create_conversation(
                self.user_ids[0],
                now=now - timedelta(days=90),
            )
            active = self.create_conversation(self.user_ids[0], now=now)
            other_user_expired = self.create_conversation(
                self.user_ids[1],
                now=now - timedelta(days=90),
            )
            for conversation in (expired, active, other_user_expired):
                append_message(
                    conversation.user_id,
                    conversation.id,
                    role="user",
                    content="Stored message.",
                    now=conversation.last_meaningful_at,
                )
            expired_id = expired.id
            active_id = active.id
            other_expired_id = other_user_expired.id

            self.assertEqual(purge_expired_conversations(now=now), 2)
            self.assertEqual(purge_expired_conversations(now=now), 0)
            self.assertIsNone(db.session.get(BuddyConversation, expired_id))
            self.assertIsNone(
                db.session.scalar(
                    select(BuddyMessage).where(
                        BuddyMessage.conversation_id == expired_id
                    )
                )
            )
            self.assertIsNone(
                db.session.get(BuddyConversation, other_expired_id)
            )
            self.assertIsNotNone(db.session.get(BuddyConversation, active_id))
            self.assertEqual(
                db.session.scalar(
                    select(func.count())
                    .select_from(BuddyMessage)
                    .where(BuddyMessage.conversation_id == active_id)
                ),
                1,
            )

    def test_delete_all_is_scoped_and_repeated_delete_is_safe(self):
        with self.app.app_context():
            owned = self.create_conversation(self.user_ids[0])
            other = self.create_conversation(self.user_ids[1])
            owned_id = owned.id
            other_id = other.id
            for conversation in (owned, other):
                append_message(
                    conversation.user_id,
                    conversation.id,
                    role="assistant",
                    content="Hint.",
                )
            self.assertEqual(
                delete_all_saved_conversations(self.user_ids[0]),
                1,
            )
            self.assertEqual(
                delete_all_saved_conversations(self.user_ids[0]),
                0,
            )
            self.assertIsNone(db.session.get(BuddyConversation, owned_id))
            self.assertIsNotNone(db.session.get(BuddyConversation, other_id))
            self.assertIsNone(
                db.session.scalar(
                    select(BuddyMessage).where(
                        BuddyMessage.conversation_id == owned_id
                    )
                )
            )

    def test_memory_is_off_without_settings_and_creation_requires_opt_in(self):
        with self.app.app_context():
            self.assertFalse(is_memory_enabled(self.user_ids[0]))
            with self.assertRaises(MemoryDisabled):
                self.create_memory(self.user_ids[0])
            self.enable_memory(self.user_ids[0])
            with self.assertRaises(LearnerApprovalRequired):
                create_memory_item(
                    self.user_ids[0],
                    category="learning_goal",
                    content="Learn Python.",
                    learner_approved=False,
                )
            self.assertEqual(list_memory_items(self.user_ids[0]), [])

    def test_enabling_memory_records_explicit_consent_metadata(self):
        now = utc_now()
        with self.app.app_context():
            self.assertTrue(
                set_memory_enabled(
                    self.user_ids[0],
                    enabled=True,
                    policy_version="memory-policy-v2",
                    now=now,
                )
            )
            user = db.session.get(User, self.user_ids[0])
            self.assertTrue(user.buddy_memory_enabled)
            self.assertEqual(
                user.buddy_privacy_settings.memory_consent_at,
                now,
            )
            self.assertEqual(
                user.buddy_privacy_settings.memory_policy_version,
                "memory-policy-v2",
            )

    def test_sensitive_memory_is_rejected(self):
        with self.app.app_context():
            self.enable_memory(self.user_ids[0])
            for unsafe_content in (
                "password: my-secret",
                "API key = sk-abcdefghijklmnop1234",
                "Contact learner@example.com",
            ):
                with self.subTest(content=unsafe_content):
                    with self.assertRaises(InvalidBuddyInput):
                        self.create_memory(self.user_ids[0], unsafe_content)

    def test_unowned_memory_cannot_be_read_edited_or_deleted(self):
        with self.app.app_context():
            self.enable_memory(self.user_ids[0])
            self.enable_memory(self.user_ids[1])
            item = self.create_memory(self.user_ids[0])
            with self.assertRaises(BuddyResourceNotFound):
                get_memory_item(self.user_ids[1], item.id)
            with self.assertRaises(BuddyResourceNotFound):
                edit_memory_item(
                    self.user_ids[1],
                    item.id,
                    category="learning_focus",
                    content="Changed.",
                    learner_approved=True,
                )
            with self.assertRaises(BuddyResourceNotFound):
                delete_memory_item(self.user_ids[1], item.id)
            self.assertEqual(len(list_memory_items(self.user_ids[0])), 1)

    def test_owned_memory_can_be_edited_and_deleted(self):
        with self.app.app_context():
            self.enable_memory(self.user_ids[0])
            item = self.create_memory(self.user_ids[0])
            item_id = item.id
            edited = edit_memory_item(
                self.user_ids[0],
                item.id,
                category="learning_focus",
                content="Focus on loops.",
                learner_approved=True,
            )
            self.assertEqual(edited.category, "learning_focus")
            self.assertEqual(edited.content, "Focus on loops.")
            delete_memory_item(self.user_ids[0], item.id)
            self.assertEqual(list_memory_items(self.user_ids[0]), [])

    def test_disabling_memory_requires_confirmation_without_changing_state(self):
        with self.app.app_context():
            self.enable_memory(self.user_ids[0])
            item = self.create_memory(self.user_ids[0])
            settings = db.session.get(
                User,
                self.user_ids[0],
            ).buddy_privacy_settings
            consent_at = settings.memory_consent_at
            with self.assertRaises(ConfirmationRequired):
                set_memory_enabled(self.user_ids[0], enabled=False)
            db.session.expire_all()
            settings = db.session.get(
                User,
                self.user_ids[0],
            ).buddy_privacy_settings
            self.assertTrue(settings.memory_enabled)
            self.assertEqual(settings.memory_consent_at, consent_at)
            self.assertIsNotNone(db.session.get(BuddyMemoryItem, item.id))

    def test_confirmed_disable_deletes_memory_and_clears_consent(self):
        with self.app.app_context():
            self.enable_memory(self.user_ids[0])
            item = self.create_memory(self.user_ids[0])
            item_id = item.id
            self.assertFalse(
                set_memory_enabled(
                    self.user_ids[0],
                    enabled=False,
                    confirm_delete_existing=True,
                )
            )
            settings = db.session.get(
                User,
                self.user_ids[0],
            ).buddy_privacy_settings
            self.assertFalse(settings.memory_enabled)
            self.assertIsNone(settings.memory_consent_at)
            self.assertIsNone(settings.memory_policy_version)
            self.assertIsNone(db.session.get(BuddyMemoryItem, item_id))

    def test_failed_memory_disable_rolls_back_deletion_and_preference(self):
        with self.app.app_context():
            self.enable_memory(self.user_ids[0])
            item = self.create_memory(self.user_ids[0])
            session = db.session()
            with patch.object(session, "commit", side_effect=RuntimeError("commit failed")):
                with self.assertRaisesRegex(RuntimeError, "commit failed"):
                    set_memory_enabled(
                        self.user_ids[0],
                        enabled=False,
                        confirm_delete_existing=True,
                    )
            db.session.expire_all()
            settings = db.session.get(
                User,
                self.user_ids[0],
            ).buddy_privacy_settings
            self.assertTrue(settings.memory_enabled)
            self.assertIsNotNone(db.session.get(BuddyMemoryItem, item.id))

    def test_failed_message_append_rolls_back_message_and_activity(self):
        now = utc_now()
        with self.app.app_context():
            conversation = self.create_conversation(self.user_ids[0], now=now)
            session = db.session()
            with patch.object(session, "commit", side_effect=RuntimeError("commit failed")):
                with self.assertRaisesRegex(RuntimeError, "commit failed"):
                    append_message(
                        self.user_ids[0],
                        conversation.id,
                        role="user",
                        content="Will not be stored.",
                        now=now + timedelta(days=1),
                    )
            db.session.expire_all()
            refreshed = db.session.get(BuddyConversation, conversation.id)
            self.assertEqual(refreshed.last_meaningful_at, now)
            self.assertEqual(refreshed.expires_at, now + timedelta(days=90))
            self.assertEqual(
                db.session.scalar(
                    select(func.count())
                    .select_from(BuddyMessage)
                    .where(BuddyMessage.conversation_id == conversation.id)
                ),
                0,
            )

    def test_retention_cli_is_repeatable_on_isolated_database(self):
        now = utc_now()
        with self.app.app_context():
            self.create_conversation(
                self.user_ids[0],
                now=now - timedelta(days=90),
            )
        first = self.app.test_cli_runner().invoke(
            args=["purge-buddy-conversations"]
        )
        second = self.app.test_cli_runner().invoke(
            args=["purge-buddy-conversations"]
        )
        self.assertEqual(first.exit_code, 0, first.output)
        self.assertIn("Purged 1 expired Buddy conversations.", first.output)
        self.assertEqual(second.exit_code, 0, second.output)
        self.assertIn("Purged 0 expired Buddy conversations.", second.output)


if __name__ == "__main__":
    unittest.main()
