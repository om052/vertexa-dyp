"""add Buddy conversation, memory, and privacy storage

Revision ID: b7c4e91a6d20
Revises: a81f2d7c9b44
Create Date: 2026-10-11 14:58:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "b7c4e91a6d20"
down_revision = "a81f2d7c9b44"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "buddy_conversations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("history_consent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("history_policy_version", sa.String(length=40), nullable=False),
        sa.Column("last_meaningful_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "length(trim(id)) > 0",
            name="ck_buddy_conversations_id_nonempty",
        ),
        sa.CheckConstraint(
            "length(trim(history_policy_version)) BETWEEN 1 AND 40",
            name="ck_buddy_conversations_policy_version_length",
        ),
        sa.CheckConstraint(
            "last_meaningful_at >= created_at",
            name="ck_buddy_conversations_activity_after_creation",
        ),
        sa.CheckConstraint(
            "expires_at > last_meaningful_at",
            name="ck_buddy_conversations_expiry_after_activity",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_buddy_conversations_owner_expiry_activity",
        "buddy_conversations",
        ["user_id", "expires_at", "last_meaningful_at"],
        unique=False,
    )
    op.create_index(
        "ix_buddy_conversations_expires_at",
        "buddy_conversations",
        ["expires_at"],
        unique=False,
    )

    op.create_table(
        "buddy_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("content", sa.String(length=12000), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "role IN ('user', 'assistant')",
            name="ck_buddy_messages_role",
        ),
        sa.CheckConstraint(
            "sequence >= 0",
            name="ck_buddy_messages_sequence_nonnegative",
        ),
        sa.CheckConstraint(
            "length(trim(content)) BETWEEN 1 AND 12000",
            name="ck_buddy_messages_content_length",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["buddy_conversations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "conversation_id",
            "sequence",
            name="uq_buddy_messages_conversation_sequence",
        ),
    )

    op.create_table(
        "buddy_memory_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("content", sa.String(length=500), nullable=False),
        sa.Column("learner_approved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "length(trim(id)) > 0",
            name="ck_buddy_memory_items_id_nonempty",
        ),
        sa.CheckConstraint(
            "category IN ('learning_goal', 'explanation_preference', "
            "'learning_focus')",
            name="ck_buddy_memory_items_category",
        ),
        sa.CheckConstraint(
            "length(trim(content)) BETWEEN 1 AND 500",
            name="ck_buddy_memory_items_content_length",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_buddy_memory_items_user_updated",
        "buddy_memory_items",
        ["user_id", "updated_at"],
        unique=False,
    )

    op.create_table(
        "buddy_privacy_settings",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column(
            "memory_enabled",
            sa.Boolean(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("memory_consent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("memory_policy_version", sa.String(length=40), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "memory_enabled = 0 OR "
            "(memory_consent_at IS NOT NULL "
            "AND memory_policy_version IS NOT NULL "
            "AND length(trim(memory_policy_version)) BETWEEN 1 AND 40)",
            name="ck_buddy_privacy_settings_memory_consent",
        ),
        sa.CheckConstraint(
            "memory_policy_version IS NULL OR "
            "length(trim(memory_policy_version)) BETWEEN 1 AND 40",
            name="ck_buddy_privacy_settings_policy_version_length",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id"),
    )


def downgrade():
    op.drop_table("buddy_privacy_settings")
    op.drop_index(
        "ix_buddy_memory_items_user_updated",
        table_name="buddy_memory_items",
    )
    op.drop_table("buddy_memory_items")
    op.drop_table("buddy_messages")
    op.drop_index(
        "ix_buddy_conversations_expires_at",
        table_name="buddy_conversations",
    )
    op.drop_index(
        "ix_buddy_conversations_owner_expiry_activity",
        table_name="buddy_conversations",
    )
    op.drop_table("buddy_conversations")
