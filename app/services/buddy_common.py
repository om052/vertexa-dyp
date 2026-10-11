import re

from app.extensions import db


class BuddyServiceError(Exception):
    """Base error for invalid or unavailable Buddy service operations."""


class ConsentRequired(BuddyServiceError):
    """Raised when an operation requires explicit learner consent."""


class InvalidBuddyInput(BuddyServiceError):
    """Raised when service inputs violate Buddy domain constraints."""


class BuddyResourceNotFound(BuddyServiceError):
    """Raised when a resource is absent, expired, or not owned by the user."""


class MemoryDisabled(BuddyServiceError):
    """Raised when persistent memory is disabled for the learner."""


class LearnerApprovalRequired(BuddyServiceError):
    """Raised when a learner has not explicitly approved a memory item."""


class ConfirmationRequired(BuddyServiceError):
    """Raised when destructive privacy changes lack explicit confirmation."""


_UUID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-"
    r"[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
)


def validated_user_id(user_id: str) -> str:
    if not isinstance(user_id, str) or not _UUID_PATTERN.fullmatch(user_id):
        raise InvalidBuddyInput("A valid authenticated user ID is required.")
    return user_id


def validated_resource_id(resource_id: str, label: str) -> str:
    if not isinstance(resource_id, str) or not _UUID_PATTERN.fullmatch(resource_id):
        raise InvalidBuddyInput(f"A valid {label} ID is required.")
    return resource_id


def commit_changes() -> None:
    try:
        db.session.flush()
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
