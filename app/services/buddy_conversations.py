import uuid
from datetime import datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import selectinload

from app.extensions import db
from app.models import BuddyConversation, BuddyMessage, utc_now
from app.services.buddy_common import (
    BuddyResourceNotFound,
    ConsentRequired,
    InvalidBuddyInput,
    commit_changes,
    validated_resource_id,
    validated_user_id,
)


HISTORY_POLICY_VERSION_MAX_LENGTH = 40
MESSAGE_MAX_LENGTH = 12000
CONVERSATION_RETENTION = timedelta(days=90)


def create_saved_conversation(
    user_id: str,
    *,
    history_consent: bool,
    policy_version: str,
    now: datetime | None = None,
) -> BuddyConversation:
    """Persist a conversation only after explicit history consent."""
    user_id = validated_user_id(user_id)
    if history_consent is not True:
        raise ConsentRequired("Explicit history consent is required.")
    if (
        not isinstance(policy_version, str)
        or not policy_version.strip()
        or len(policy_version.strip()) > HISTORY_POLICY_VERSION_MAX_LENGTH
    ):
        raise InvalidBuddyInput("A valid history policy version is required.")

    created_at = now or utc_now()
    if created_at.tzinfo is None:
        raise InvalidBuddyInput("Conversation timestamps must include a timezone.")
    created_at = created_at.astimezone(utc_now().tzinfo)
    conversation = BuddyConversation(
        id=str(uuid.uuid4()),
        user_id=user_id,
        history_consent_at=created_at,
        history_policy_version=policy_version.strip(),
        created_at=created_at,
        updated_at=created_at,
        last_meaningful_at=created_at,
        expires_at=created_at + CONVERSATION_RETENTION,
    )
    db.session.add(conversation)
    commit_changes()
    return conversation


def get_saved_conversation(
    user_id: str,
    conversation_id: str,
    *,
    now: datetime | None = None,
) -> BuddyConversation:
    """Return an owned, unexpired conversation with ordered messages."""
    user_id = validated_user_id(user_id)
    conversation_id = validated_resource_id(conversation_id, "conversation")
    current_time = now or utc_now()
    conversation = db.session.scalar(
        select(BuddyConversation)
        .options(selectinload(BuddyConversation.messages))
        .where(
            BuddyConversation.id == conversation_id,
            BuddyConversation.user_id == user_id,
            BuddyConversation.expires_at > current_time,
        )
    )
    if conversation is None:
        raise BuddyResourceNotFound("Conversation not found.")
    return conversation


def _get_owned_conversation(
    user_id: str,
    conversation_id: str,
) -> BuddyConversation:
    user_id = validated_user_id(user_id)
    conversation_id = validated_resource_id(conversation_id, "conversation")
    conversation = db.session.scalar(
        select(BuddyConversation).where(
            BuddyConversation.id == conversation_id,
            BuddyConversation.user_id == user_id,
        )
    )
    if conversation is None:
        raise BuddyResourceNotFound("Conversation not found.")
    return conversation


def list_saved_conversations(
    user_id: str,
    *,
    now: datetime | None = None,
) -> list[BuddyConversation]:
    """List only the user's conversations whose expiry is strictly in future."""
    user_id = validated_user_id(user_id)
    current_time = now or utc_now()
    return list(
        db.session.scalars(
            select(BuddyConversation)
            .where(
                BuddyConversation.user_id == user_id,
                BuddyConversation.expires_at > current_time,
            )
            .order_by(
                BuddyConversation.last_meaningful_at.desc(),
                BuddyConversation.id,
            )
        ).all()
    )


def get_saved_messages(
    user_id: str,
    conversation_id: str,
    *,
    now: datetime | None = None,
) -> list[BuddyMessage]:
    """Retrieve authoritative saved messages from the database."""
    conversation = get_saved_conversation(
        user_id,
        conversation_id,
        now=now,
    )
    return list(conversation.messages)


def append_message(
    user_id: str,
    conversation_id: str,
    *,
    role: str,
    content: str,
    now: datetime | None = None,
) -> BuddyMessage:
    """Append one owned conversation message using the next sequence number."""
    if not isinstance(role, str) or role not in {"user", "assistant"}:
        raise InvalidBuddyInput("Message role must be user or assistant.")
    if (
        not isinstance(content, str)
        or not content.strip()
        or len(content) > MESSAGE_MAX_LENGTH
    ):
        raise InvalidBuddyInput(
            f"Message content must contain 1 to {MESSAGE_MAX_LENGTH} characters."
        )

    conversation = get_saved_conversation(
        user_id,
        conversation_id,
        now=now,
    )
    current_time = now or utc_now()
    if current_time.tzinfo is None:
        raise InvalidBuddyInput("Message timestamps must include a timezone.")
    current_time = current_time.astimezone(utc_now().tzinfo)

    next_sequence = db.session.scalar(
        select(func.coalesce(func.max(BuddyMessage.sequence), -1) + 1).where(
            BuddyMessage.conversation_id == conversation.id
        )
    )
    message = BuddyMessage(
        conversation_id=conversation.id,
        role=role,
        sequence=next_sequence,
        content=content.strip(),
        created_at=current_time,
    )
    db.session.add(message)
    if role == "user":
        conversation.last_meaningful_at = current_time
        conversation.expires_at = current_time + CONVERSATION_RETENTION
    commit_changes()
    return message


def append_exchange(
    user_id: str,
    conversation_id: str,
    *,
    user_content: str,
    assistant_content: str,
    now: datetime | None = None,
) -> tuple[BuddyMessage, BuddyMessage]:
    """Append one complete user/assistant turn in a single transaction."""
    conversation = get_saved_conversation(
        user_id,
        conversation_id,
        now=now,
    )
    current_time = now or utc_now()
    if current_time.tzinfo is None:
        raise InvalidBuddyInput("Message timestamps must include a timezone.")
    current_time = current_time.astimezone(utc_now().tzinfo)
    contents = (user_content, assistant_content)
    if any(
        not isinstance(content, str)
        or not content.strip()
        or len(content) > MESSAGE_MAX_LENGTH
        for content in contents
    ):
        raise InvalidBuddyInput(
            f"Message content must contain 1 to {MESSAGE_MAX_LENGTH} characters."
        )

    next_sequence = db.session.scalar(
        select(func.coalesce(func.max(BuddyMessage.sequence), -1) + 1).where(
            BuddyMessage.conversation_id == conversation.id
        )
    )
    user_message = BuddyMessage(
        conversation_id=conversation.id,
        role="user",
        sequence=next_sequence,
        content=user_content.strip(),
        created_at=current_time,
    )
    assistant_message = BuddyMessage(
        conversation_id=conversation.id,
        role="assistant",
        sequence=next_sequence + 1,
        content=assistant_content.strip(),
        created_at=current_time,
    )
    conversation.last_meaningful_at = current_time
    conversation.expires_at = current_time + CONVERSATION_RETENTION
    db.session.add_all((user_message, assistant_message))
    commit_changes()
    return user_message, assistant_message


def create_saved_conversation_with_exchange(
    user_id: str,
    *,
    history_consent: bool,
    policy_version: str,
    user_content: str,
    assistant_content: str,
    now: datetime | None = None,
) -> tuple[BuddyConversation, tuple[BuddyMessage, BuddyMessage]]:
    """Create a consented conversation and its first turn atomically."""
    user_id = validated_user_id(user_id)
    if history_consent is not True:
        raise ConsentRequired("Explicit history consent is required.")
    if (
        not isinstance(policy_version, str)
        or not policy_version.strip()
        or len(policy_version.strip()) > HISTORY_POLICY_VERSION_MAX_LENGTH
    ):
        raise InvalidBuddyInput("A valid history policy version is required.")
    contents = (user_content, assistant_content)
    if any(
        not isinstance(content, str)
        or not content.strip()
        or len(content) > MESSAGE_MAX_LENGTH
        for content in contents
    ):
        raise InvalidBuddyInput(
            f"Message content must contain 1 to {MESSAGE_MAX_LENGTH} characters."
        )
    created_at = now or utc_now()
    if created_at.tzinfo is None:
        raise InvalidBuddyInput("Conversation timestamps must include a timezone.")
    created_at = created_at.astimezone(utc_now().tzinfo)
    conversation = BuddyConversation(
        id=str(uuid.uuid4()),
        user_id=user_id,
        history_consent_at=created_at,
        history_policy_version=policy_version.strip(),
        created_at=created_at,
        updated_at=created_at,
        last_meaningful_at=created_at,
        expires_at=created_at + CONVERSATION_RETENTION,
    )
    user_message = BuddyMessage(
        conversation=conversation,
        role="user",
        sequence=0,
        content=user_content.strip(),
        created_at=created_at,
    )
    assistant_message = BuddyMessage(
        conversation=conversation,
        role="assistant",
        sequence=1,
        content=assistant_content.strip(),
        created_at=created_at,
    )
    db.session.add(conversation)
    db.session.add_all((user_message, assistant_message))
    commit_changes()
    return conversation, (user_message, assistant_message)


def delete_saved_conversation(user_id: str, conversation_id: str) -> None:
    """Delete one owned conversation; messages cascade with it."""
    conversation = _get_owned_conversation(user_id, conversation_id)
    try:
        db.session.delete(conversation)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


def delete_all_saved_conversations(user_id: str) -> int:
    """Delete all saved conversations belonging to one user."""
    user_id = validated_user_id(user_id)
    try:
        result = db.session.execute(
            delete(BuddyConversation)
            .where(BuddyConversation.user_id == user_id)
            .execution_options(synchronize_session=False)
        )
        deleted_count = result.rowcount or 0
        db.session.commit()
        return deleted_count
    except Exception:
        db.session.rollback()
        raise
