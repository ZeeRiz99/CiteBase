"""Text recognition (OCR) facts per document version.

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-17
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE document_versions ADD COLUMN ocr_pages integer NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE document_versions ADD COLUMN ocr_confidence real")


def downgrade() -> None:
    op.execute("ALTER TABLE document_versions DROP COLUMN IF EXISTS ocr_confidence")
    op.execute("ALTER TABLE document_versions DROP COLUMN IF EXISTS ocr_pages")
