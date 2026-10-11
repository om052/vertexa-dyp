from datetime import datetime

from sqlalchemy import delete

from app.extensions import db
from app.models import BuddyConversation, utc_now
from app.services.buddy_common import InvalidBuddyInput


def purge_expired_conversations(*, now: datetime | None = None) -> int:
    """Delete expired conversations and cascading messages; safe to repeat."""
    cutoff = now or utc_now()
    if cutoff.tzinfo is None:
        raise InvalidBuddyInput("Retention cutoff must include a timezone.")
    cutoff = cutoff.astimezone(utc_now().tzinfo)
    try:
        result = db.session.execute(
            delete(BuddyConversation)
            .where(BuddyConversation.expires_at <= cutoff)
            .execution_options(synchronize_session=False)
        )
        deleted_count = result.rowcount or 0
        db.session.commit()
        return deleted_count
    except Exception:
        db.session.rollback()
        raise
