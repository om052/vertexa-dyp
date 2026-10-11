import re
import uuid
from datetime import datetime

from sqlalchemy import delete, func, select

from app.extensions import db
from app.models import BuddyMemoryItem, BuddyPrivacySettings, utc_now
from app.services.buddy_common import (
    BuddyResourceNotFound,
    ConfirmationRequired,
    InvalidBuddyInput,
    LearnerApprovalRequired,
    MemoryDisabled,
    commit_changes,
    validated_resource_id,
    validated_user_id,
)


MEMORY_POLICY_VERSION_MAX_LENGTH = 40
MEMORY_CONTENT_MAX_LENGTH = 500
MEMORY_CATEGORIES = frozenset(
    {"learning_goal", "explanation_preference", "learning_focus"}
)
_SENSITIVE_CONTENT_PATTERNS = (
    re.compile(
        r"\b(?:password|passcode|secret|api[\s_-]?key|access[\s_-]?token|"
        r"auth(?:entication)?[\s_-]?token|credential)\b"
        r"\s*(?:is|=|:)\s*\S+",
        re.IGNORECASE,
    ),
    re.compile(r"\bbearer\s+[A-Za-z0-9._~+/=-]{12,}", re.IGNORECASE),
    re.compile(r"\bsk-[A-Za-z0-9]{16,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\b[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
               r"[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
)


def get_privacy_settings(user_id: str) -> BuddyPrivacySettings | None:
    """Return the user's settings; a missing row means memory is disabled."""
    user_id = validated_user_id(user_id)
    return db.session.get(BuddyPrivacySettings, user_id)


def is_memory_enabled(user_id: str) -> bool:
    """Treat both missing settings and the default preference as disabled."""
    settings = get_privacy_settings(user_id)
    return bool(settings and settings.memory_enabled)


def set_memory_enabled(
    user_id: str,
    *,
    enabled: bool,
    policy_version: str | None = None,
    confirm_delete_existing: bool = False,
    now: datetime | None = None,
) -> bool:
    """Explicitly opt in or disable and, with confirmation, erase memory."""
    user_id = validated_user_id(user_id)
    if not isinstance(enabled, bool):
        raise InvalidBuddyInput("Memory enabled must be a boolean.")
    current_time = now or utc_now()
    if current_time.tzinfo is None:
        raise InvalidBuddyInput("Privacy timestamps must include a timezone.")
    current_time = current_time.astimezone(utc_now().tzinfo)
    settings = db.session.get(BuddyPrivacySettings, user_id)

    if enabled:
        if (
            not isinstance(policy_version, str)
            or not policy_version.strip()
            or len(policy_version.strip()) > MEMORY_POLICY_VERSION_MAX_LENGTH
        ):
            raise InvalidBuddyInput(
                "A valid memory policy version is required to enable memory."
            )
        if settings is None:
            settings = BuddyPrivacySettings(user_id=user_id)
            db.session.add(settings)
        settings.memory_enabled = True
        settings.memory_consent_at = current_time
        settings.memory_policy_version = policy_version.strip()
        settings.updated_at = current_time
        commit_changes()
        return True

    if settings is None:
        return False

    item_count = db.session.scalar(
        select(func.count())
        .select_from(BuddyMemoryItem)
        .where(BuddyMemoryItem.user_id == user_id)
    )
    if item_count and confirm_delete_existing is not True:
        raise ConfirmationRequired(
            "Confirm deletion of existing Buddy memory before disabling it."
        )

    try:
        if item_count:
            db.session.execute(
                delete(BuddyMemoryItem)
                .where(BuddyMemoryItem.user_id == user_id)
                .execution_options(synchronize_session=False)
            )
        settings.memory_enabled = False
        settings.memory_consent_at = None
        settings.memory_policy_version = None
        settings.updated_at = current_time
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return False


def _validate_memory_content(content: str) -> str:
    if not isinstance(content, str):
        raise InvalidBuddyInput("Memory content must be text.")
    normalized = content.strip()
    if not normalized or len(normalized) > MEMORY_CONTENT_MAX_LENGTH:
        raise InvalidBuddyInput(
            f"Memory content must contain 1 to {MEMORY_CONTENT_MAX_LENGTH} "
            "characters."
        )
    if any(pattern.search(normalized) for pattern in _SENSITIVE_CONTENT_PATTERNS):
        raise InvalidBuddyInput(
            "Memory cannot contain credentials, contact details, or secrets."
        )
    return normalized


def _validate_category(category: str) -> str:
    if not isinstance(category, str) or category not in MEMORY_CATEGORIES:
        raise InvalidBuddyInput("Choose a permitted Buddy memory category.")
    return category


def create_memory_item(
    user_id: str,
    *,
    category: str,
    content: str,
    learner_approved: bool,
    now: datetime | None = None,
) -> BuddyMemoryItem:
    """Store a memory item only with opt-in and explicit learner approval."""
    user_id = validated_user_id(user_id)
    if learner_approved is not True:
        raise LearnerApprovalRequired(
            "Explicit learner approval is required to save memory."
        )
    if not is_memory_enabled(user_id):
        raise MemoryDisabled("Persistent Buddy memory is disabled.")
    current_time = now or utc_now()
    if current_time.tzinfo is None:
        raise InvalidBuddyInput("Memory timestamps must include a timezone.")
    current_time = current_time.astimezone(utc_now().tzinfo)
    item = BuddyMemoryItem(
        id=str(uuid.uuid4()),
        user_id=user_id,
        category=_validate_category(category),
        content=_validate_memory_content(content),
        learner_approved_at=current_time,
        created_at=current_time,
        updated_at=current_time,
    )
    db.session.add(item)
    commit_changes()
    return item


def list_memory_items(user_id: str) -> list[BuddyMemoryItem]:
    """List this learner's own memory items in a stable order."""
    user_id = validated_user_id(user_id)
    return list(
        db.session.scalars(
            select(BuddyMemoryItem)
            .where(BuddyMemoryItem.user_id == user_id)
            .order_by(BuddyMemoryItem.created_at, BuddyMemoryItem.id)
        ).all()
    )


def get_memory_item(user_id: str, item_id: str) -> BuddyMemoryItem:
    """Fetch an item only when it belongs to the requesting learner."""
    user_id = validated_user_id(user_id)
    item_id = validated_resource_id(item_id, "memory item")
    item = db.session.scalar(
        select(BuddyMemoryItem).where(
            BuddyMemoryItem.id == item_id,
            BuddyMemoryItem.user_id == user_id,
        )
    )
    if item is None:
        raise BuddyResourceNotFound("Buddy memory item not found.")
    return item


def edit_memory_item(
    user_id: str,
    item_id: str,
    *,
    category: str,
    content: str,
    learner_approved: bool,
    now: datetime | None = None,
) -> BuddyMemoryItem:
    """Edit an owned memory item after the learner approves its new contents."""
    if learner_approved is not True:
        raise LearnerApprovalRequired(
            "Explicit learner approval is required to update memory."
        )
    item = get_memory_item(user_id, item_id)
    current_time = now or utc_now()
    if current_time.tzinfo is None:
        raise InvalidBuddyInput("Memory timestamps must include a timezone.")
    item.category = _validate_category(category)
    item.content = _validate_memory_content(content)
    item.learner_approved_at = current_time.astimezone(utc_now().tzinfo)
    item.updated_at = item.learner_approved_at
    commit_changes()
    return item


def delete_memory_item(user_id: str, item_id: str) -> None:
    """Delete one memory item only when it belongs to the requesting learner."""
    item = get_memory_item(user_id, item_id)
    try:
        db.session.delete(item)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
