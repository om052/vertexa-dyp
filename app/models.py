import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Table,
    UniqueConstraint,
)
from sqlalchemy.types import DateTime, TypeDecorator

from app.extensions import db


lesson_prerequisites = Table(
    "lesson_prerequisites",
    db.metadata,
    db.Column(
        "lesson_id",
        db.Integer,
        ForeignKey("lessons.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column(
        "prerequisite_id",
        db.Integer,
        ForeignKey("lessons.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    CheckConstraint(
        "lesson_id != prerequisite_id",
        name="ck_lesson_prerequisites_not_self",
    ),
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator):
    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, _dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("Timestamps must include a timezone.")
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(self, value, _dialect):
        if value is None or value.tzinfo is not None:
            return value
        return value.replace(tzinfo=timezone.utc)


class TimestampMixin:
    created_at = db.Column(UTCDateTime(), nullable=False, default=utc_now)
    updated_at = db.Column(
        UTCDateTime(),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )


class User(TimestampMixin, db.Model):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("length(trim(id)) > 0", name="ck_users_id_nonempty"),
        CheckConstraint(
            "username IS NULL OR length(trim(username)) BETWEEN 3 AND 30",
            name="ck_users_username_length",
        ),
        CheckConstraint(
            "email IS NULL OR length(trim(email)) BETWEEN 3 AND 254",
            name="ck_users_email_length",
        ),
        CheckConstraint(
            "password_hash IS NULL OR length(trim(password_hash)) > 0",
            name="ck_users_password_hash_nonempty",
        ),
        UniqueConstraint("username", name="uq_users_username"),
        UniqueConstraint("email", name="uq_users_email"),
    )

    id = db.Column(
        db.String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    username = db.Column(db.String(30), nullable=True)
    email = db.Column(db.String(254), nullable=True)
    password_hash = db.Column(db.String(512), nullable=True)
    profile = db.relationship(
        "LearnerProfile",
        back_populates="user",
        uselist=False,
        passive_deletes=True,
    )


class Language(db.Model):
    __tablename__ = "languages"
    __table_args__ = (
        CheckConstraint("length(trim(code)) > 0", name="ck_languages_code_nonempty"),
        CheckConstraint("length(trim(name)) > 0", name="ck_languages_name_nonempty"),
        CheckConstraint(
            "position >= 0",
            name="ck_languages_position_nonnegative",
        ),
        CheckConstraint(
            "description IS NULL OR length(trim(description)) > 0",
            name="ck_languages_description_nonempty",
        ),
    )

    code = db.Column(db.String(32), primary_key=True)
    name = db.Column(db.String(80), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=True)
    position = db.Column(
        db.Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    topics = db.relationship(
        "Topic",
        back_populates="language",
        order_by="(Topic.position, Topic.id)",
        passive_deletes=True,
    )


class LearnerProfile(TimestampMixin, db.Model):
    __tablename__ = "learner_profiles"
    __table_args__ = (
        CheckConstraint(
            "display_name IS NULL OR length(trim(display_name)) > 0",
            name="ck_learner_profiles_display_name_nonempty",
        ),
        CheckConstraint(
            "bio IS NULL OR length(trim(bio)) BETWEEN 1 AND 280",
            name="ck_learner_profiles_bio_length",
        ),
    )

    user_id = db.Column(
        db.String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    display_name = db.Column(db.String(80), nullable=True)
    bio = db.Column(db.String(280), nullable=True)
    preferred_language_code = db.Column(
        db.String(32),
        ForeignKey("languages.code", ondelete="SET NULL"),
        nullable=True,
    )
    user = db.relationship("User", back_populates="profile")
    preferred_language = db.relationship("Language")


class Topic(TimestampMixin, db.Model):
    __tablename__ = "topics"
    __table_args__ = (
        UniqueConstraint("language_code", "slug", name="uq_topics_language_slug"),
        CheckConstraint("length(trim(slug)) > 0", name="ck_topics_slug_nonempty"),
        CheckConstraint("length(trim(title)) > 0", name="ck_topics_title_nonempty"),
        CheckConstraint(
            "description IS NULL OR length(trim(description)) > 0",
            name="ck_topics_description_nonempty",
        ),
        CheckConstraint("position >= 0", name="ck_topics_position_nonnegative"),
        CheckConstraint(
            "difficulty IN ('beginner', 'intermediate', 'advanced')",
            name="ck_topics_difficulty",
        ),
        Index("ix_topics_language_code", "language_code"),
    )

    id = db.Column(db.Integer, primary_key=True)
    language_code = db.Column(
        db.String(32),
        ForeignKey("languages.code", ondelete="RESTRICT"),
        nullable=False,
    )
    slug = db.Column(db.String(100), nullable=False)
    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, nullable=True)
    position = db.Column(
        db.Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    difficulty = db.Column(
        db.String(20),
        nullable=False,
        default="beginner",
        server_default="beginner",
    )
    language = db.relationship("Language", back_populates="topics")
    lessons = db.relationship(
        "Lesson",
        back_populates="topic",
        order_by="(Lesson.position, Lesson.id)",
        passive_deletes=True,
    )


class Lesson(TimestampMixin, db.Model):
    __tablename__ = "lessons"
    __table_args__ = (
        UniqueConstraint("topic_id", "slug", name="uq_lessons_topic_slug"),
        UniqueConstraint("topic_id", "position", name="uq_lessons_topic_position"),
        CheckConstraint("length(trim(slug)) > 0", name="ck_lessons_slug_nonempty"),
        CheckConstraint("length(trim(title)) > 0", name="ck_lessons_title_nonempty"),
        CheckConstraint(
            "description IS NULL OR length(trim(description)) > 0",
            name="ck_lessons_description_nonempty",
        ),
        CheckConstraint("position >= 0", name="ck_lessons_position_nonnegative"),
    )

    id = db.Column(db.Integer, primary_key=True)
    topic_id = db.Column(
        db.Integer,
        ForeignKey("topics.id", ondelete="RESTRICT"),
        nullable=False,
    )
    slug = db.Column(db.String(100), nullable=False)
    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, nullable=True)
    content = db.Column(db.Text, nullable=False)
    position = db.Column(db.Integer, nullable=False)
    topic = db.relationship("Topic", back_populates="lessons")
    prerequisites = db.relationship(
        "Lesson",
        secondary=lesson_prerequisites,
        primaryjoin=id == lesson_prerequisites.c.lesson_id,
        secondaryjoin=id == lesson_prerequisites.c.prerequisite_id,
        back_populates="unlocks",
        order_by="(Lesson.position, Lesson.id)",
    )
    unlocks = db.relationship(
        "Lesson",
        secondary=lesson_prerequisites,
        primaryjoin=id == lesson_prerequisites.c.prerequisite_id,
        secondaryjoin=id == lesson_prerequisites.c.lesson_id,
        back_populates="prerequisites",
        order_by="(Lesson.position, Lesson.id)",
    )


class LearningProgress(TimestampMixin, db.Model):
    __tablename__ = "learning_progress"
    __table_args__ = (
        CheckConstraint(
            "status IN ('not_started', 'in_progress', 'completed')",
            name="ck_learning_progress_status",
        ),
        Index("ix_learning_progress_lesson_id", "lesson_id"),
    )

    user_id = db.Column(
        db.String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    lesson_id = db.Column(
        db.Integer,
        ForeignKey("lessons.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    status = db.Column(db.String(20), nullable=False, default="not_started")
    user = db.relationship("User")
    lesson = db.relationship("Lesson")
