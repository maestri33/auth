"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-04-25
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "app_config",
        sa.Column("key", sa.String(length=80), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "roles",
        sa.Column("name", sa.String(length=80), primary_key=True),
        sa.Column("is_staff", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_transitory", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("transitions_to", sa.String(length=80), nullable=True),
        sa.Column("requires_role", sa.String(length=80), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["transitions_to"], ["roles.name"], name="fk_roles_transitions_to_roles"
        ),
        sa.ForeignKeyConstraint(
            ["requires_role"], ["roles.name"], name="fk_roles_requires_role_roles"
        ),
    )

    op.create_table(
        "role_incompatibilities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("role_name", sa.String(length=80), nullable=False),
        sa.Column("incompatible_with", sa.String(length=80), nullable=False),
        sa.ForeignKeyConstraint(
            ["role_name"], ["roles.name"], name="fk_role_incompatibilities_role_name_roles"
        ),
        sa.ForeignKeyConstraint(
            ["incompatible_with"], ["roles.name"], name="fk_role_incompatibilities_incompatible_with_roles"
        ),
        sa.UniqueConstraint(
            "role_name", "incompatible_with", name="uq_role_incompatibilities_role_name_incompatible_with"
        ),
    )

    op.create_table(
        "users",
        sa.Column("external_id", sa.String(length=36), primary_key=True),
        sa.Column("phone", sa.String(length=32), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("phone", name="uq_users_phone"),
    )
    op.create_index("ix_users_phone", "users", ["phone"], unique=False)

    op.create_table(
        "user_roles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("external_id", sa.String(length=36), nullable=False),
        sa.Column("role_name", sa.String(length=80), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["external_id"], ["users.external_id"], name="fk_user_roles_external_id_users"
        ),
        sa.ForeignKeyConstraint(
            ["role_name"], ["roles.name"], name="fk_user_roles_role_name_roles"
        ),
        sa.UniqueConstraint(
            "external_id", "role_name", name="uq_user_roles_external_id_role_name"
        ),
    )

    op.create_table(
        "otp_challenges",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("external_id", sa.String(length=36), nullable=False),
        sa.Column("otp_hash", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("consumed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["external_id"], ["users.external_id"], name="fk_otp_challenges_external_id_users"
        ),
    )
    op.create_index("ix_otp_challenges_external_id", "otp_challenges", ["external_id"])
    op.create_index("ix_otp_challenges_expires_at", "otp_challenges", ["expires_at"])

    op.create_table(
        "oauth_clients",
        sa.Column("client_id", sa.String(length=80), primary_key=True),
        sa.Column("client_secret_hash", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("scopes", sa.Text(), nullable=False, server_default=""),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("oauth_clients")
    op.drop_index("ix_otp_challenges_expires_at", table_name="otp_challenges")
    op.drop_index("ix_otp_challenges_external_id", table_name="otp_challenges")
    op.drop_table("otp_challenges")
    op.drop_table("user_roles")
    op.drop_index("ix_users_phone", table_name="users")
    op.drop_table("users")
    op.drop_table("role_incompatibilities")
    op.drop_table("roles")
    op.drop_table("app_config")
