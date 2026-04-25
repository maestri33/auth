"""audit_events e refresh_tokens

Revision ID: 0002_audit_and_sessions
Revises: 0001_initial
Create Date: 2026-04-25
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0002_audit_and_sessions"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ts", sa.DateTime(), nullable=False),
        sa.Column("actor_type", sa.String(length=20), nullable=False),
        sa.Column("actor_id", sa.String(length=80), nullable=True),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("target_type", sa.String(length=40), nullable=True),
        sa.Column("target_id", sa.String(length=120), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("ip", sa.String(length=64), nullable=True),
    )
    op.create_index("ix_audit_events_ts", "audit_events", ["ts"])
    op.create_index("ix_audit_events_actor_id", "audit_events", ["actor_id"])
    op.create_index("ix_audit_events_action", "audit_events", ["action"])
    op.create_index("ix_audit_events_target_id", "audit_events", ["target_id"])

    op.create_table(
        "refresh_tokens",
        sa.Column("jti", sa.String(length=36), primary_key=True),
        sa.Column("external_id", sa.String(length=36), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_reason", sa.String(length=80), nullable=True),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(
            ["external_id"], ["users.external_id"], name="fk_refresh_tokens_external_id_users"
        ),
    )
    op.create_index("ix_refresh_tokens_external_id", "refresh_tokens", ["external_id"])
    op.create_index("ix_refresh_tokens_expires_at", "refresh_tokens", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_refresh_tokens_expires_at", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_external_id", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
    op.drop_index("ix_audit_events_target_id", table_name="audit_events")
    op.drop_index("ix_audit_events_action", table_name="audit_events")
    op.drop_index("ix_audit_events_actor_id", table_name="audit_events")
    op.drop_index("ix_audit_events_ts", table_name="audit_events")
    op.drop_table("audit_events")
