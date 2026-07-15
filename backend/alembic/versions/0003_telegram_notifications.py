"""telegram notifications

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-15

"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("telegram_chat_id", sa.String(32), nullable=True))
    op.add_column(
        "users",
        sa.Column(
            "telegram_notifications",
            sa.Boolean,
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "notes",
        sa.Column("reminder_sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_notes_reminder_sent_at", "notes", ["reminder_sent_at"])


def downgrade():
    op.drop_index("ix_notes_reminder_sent_at", "notes")
    op.drop_column("notes", "reminder_sent_at")
    op.drop_column("users", "telegram_notifications")
    op.drop_column("users", "telegram_chat_id")
