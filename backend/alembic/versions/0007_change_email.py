"""Email change: a single-use token sent to the new address, which it carries until confirmed.

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-18
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE token_purpose ADD VALUE IF NOT EXISTS 'change_email'")
    op.execute("ALTER TABLE auth_tokens ADD COLUMN new_email citext")


def downgrade() -> None:
    op.execute("DELETE FROM auth_tokens WHERE purpose = 'change_email'")
    op.execute("ALTER TABLE auth_tokens DROP COLUMN IF EXISTS new_email")
    # Postgres cannot drop an enum value; rebuild the type without it.
    op.execute("ALTER TYPE token_purpose RENAME TO token_purpose_old")
    op.execute("CREATE TYPE token_purpose AS ENUM ('verify_email', 'reset_password')")
    op.execute(
        "ALTER TABLE auth_tokens ALTER COLUMN purpose TYPE token_purpose "
        "USING purpose::text::token_purpose"
    )
    op.execute("DROP TYPE token_purpose_old")
