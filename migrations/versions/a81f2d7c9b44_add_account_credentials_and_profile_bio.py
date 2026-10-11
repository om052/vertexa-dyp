"""add account credentials and profile bio

Revision ID: a81f2d7c9b44
Revises: ce39ebd9f6d8
Create Date: 2026-10-11 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "a81f2d7c9b44"
down_revision = "ce39ebd9f6d8"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("username", sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column("email", sa.String(length=254), nullable=True))
        batch_op.add_column(
            sa.Column("password_hash", sa.String(length=512), nullable=True)
        )
        batch_op.create_check_constraint(
            "ck_users_username_length",
            "username IS NULL OR length(trim(username)) BETWEEN 3 AND 30",
        )
        batch_op.create_check_constraint(
            "ck_users_email_length",
            "email IS NULL OR length(trim(email)) BETWEEN 3 AND 254",
        )
        batch_op.create_check_constraint(
            "ck_users_password_hash_nonempty",
            "password_hash IS NULL OR length(trim(password_hash)) > 0",
        )
        batch_op.create_unique_constraint("uq_users_username", ["username"])
        batch_op.create_unique_constraint("uq_users_email", ["email"])

    with op.batch_alter_table("learner_profiles") as batch_op:
        batch_op.add_column(sa.Column("bio", sa.String(length=280), nullable=True))
        batch_op.create_check_constraint(
            "ck_learner_profiles_bio_length",
            "bio IS NULL OR length(trim(bio)) BETWEEN 1 AND 280",
        )


def downgrade():
    with op.batch_alter_table("learner_profiles") as batch_op:
        batch_op.drop_constraint("ck_learner_profiles_bio_length", type_="check")
        batch_op.drop_column("bio")

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("uq_users_email", type_="unique")
        batch_op.drop_constraint("uq_users_username", type_="unique")
        batch_op.drop_constraint("ck_users_password_hash_nonempty", type_="check")
        batch_op.drop_constraint("ck_users_email_length", type_="check")
        batch_op.drop_constraint("ck_users_username_length", type_="check")
        batch_op.drop_column("password_hash")
        batch_op.drop_column("email")
        batch_op.drop_column("username")
