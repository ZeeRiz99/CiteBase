"""Documents: documents, versions, extracted pages, chunks (with keyword index), RLS.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-14
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "citebase_app"
TABLES = ("documents", "document_versions", "document_pages", "chunks")


def upgrade() -> None:
    op.execute(
        "CREATE TYPE document_status AS ENUM "
        "('queued', 'extracting', 'chunking', 'embedding', 'indexed', 'failed', 'needs_ocr')"
    )

    op.execute(
        """
        CREATE TABLE documents (
            id uuid CONSTRAINT pk_documents PRIMARY KEY,
            workspace_id uuid NOT NULL
                CONSTRAINT fk_documents_workspace_id_workspaces
                REFERENCES workspaces(id) ON DELETE CASCADE,
            collection_id uuid NOT NULL
                CONSTRAINT fk_documents_collection_id_collections
                REFERENCES collections(id) ON DELETE RESTRICT,
            title varchar(255) NOT NULL,
            current_version_id uuid,
            latest_version_id uuid,
            created_by uuid
                CONSTRAINT fk_documents_created_by_users REFERENCES users(id) ON DELETE SET NULL,
            deleted_at timestamptz,
            purge_after timestamptz,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX ix_documents_workspace_live ON documents (workspace_id, deleted_at)")

    op.execute(
        """
        CREATE TABLE document_versions (
            id uuid CONSTRAINT pk_document_versions PRIMARY KEY,
            workspace_id uuid NOT NULL,
            document_id uuid NOT NULL
                CONSTRAINT fk_document_versions_document_id_documents
                REFERENCES documents(id) ON DELETE CASCADE,
            version_number integer NOT NULL,
            original_filename varchar(255) NOT NULL,
            storage_key varchar(255) NOT NULL,
            mime_type varchar(100) NOT NULL,
            file_ext varchar(10) NOT NULL,
            size_bytes bigint NOT NULL,
            content_hash varchar(64) NOT NULL,
            page_count integer,
            status document_status NOT NULL DEFAULT 'queued',
            error_code varchar(60),
            error_message text,
            extractor varchar(40),
            extractor_version varchar(40),
            chunking_config jsonb NOT NULL DEFAULT '{}'::jsonb,
            chunk_count integer NOT NULL DEFAULT 0,
            created_by uuid
                CONSTRAINT fk_document_versions_created_by_users
                REFERENCES users(id) ON DELETE SET NULL,
            indexed_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_document_versions_number UNIQUE (document_id, version_number)
        )
        """
    )
    op.execute("CREATE INDEX ix_document_versions_document_id ON document_versions (document_id)")
    op.execute(
        "CREATE INDEX ix_document_versions_workspace_hash "
        "ON document_versions (workspace_id, content_hash)"
    )

    # Circular references: added after both tables exist.
    op.execute(
        "ALTER TABLE documents ADD CONSTRAINT fk_documents_current_version_id_document_versions "
        "FOREIGN KEY (current_version_id) REFERENCES document_versions(id) ON DELETE SET NULL"
    )
    op.execute(
        "ALTER TABLE documents ADD CONSTRAINT fk_documents_latest_version_id_document_versions "
        "FOREIGN KEY (latest_version_id) REFERENCES document_versions(id) ON DELETE SET NULL"
    )

    op.execute(
        """
        CREATE TABLE document_pages (
            id uuid CONSTRAINT pk_document_pages PRIMARY KEY,
            workspace_id uuid NOT NULL,
            document_version_id uuid NOT NULL
                CONSTRAINT fk_document_pages_document_version_id_document_versions
                REFERENCES document_versions(id) ON DELETE CASCADE,
            page_number integer NOT NULL,
            heading_path text,
            text text NOT NULL,
            char_count integer NOT NULL,
            CONSTRAINT uq_document_pages_number UNIQUE (document_version_id, page_number)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE chunks (
            id uuid CONSTRAINT pk_chunks PRIMARY KEY,
            workspace_id uuid NOT NULL,
            document_id uuid NOT NULL
                CONSTRAINT fk_chunks_document_id_documents
                REFERENCES documents(id) ON DELETE CASCADE,
            document_version_id uuid NOT NULL
                CONSTRAINT fk_chunks_document_version_id_document_versions
                REFERENCES document_versions(id) ON DELETE CASCADE,
            collection_id uuid NOT NULL,
            chunk_index integer NOT NULL,
            page_start integer NOT NULL,
            page_end integer NOT NULL,
            section_title text,
            char_start integer NOT NULL,
            char_end integer NOT NULL,
            text text NOT NULL,
            token_count integer NOT NULL,
            content_hash varchar(64) NOT NULL,
            tsv tsvector,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_chunks_version_index UNIQUE (document_version_id, chunk_index)
        )
        """
    )
    op.execute("CREATE INDEX ix_chunks_tsv ON chunks USING gin (tsv)")
    op.execute("CREATE INDEX ix_chunks_workspace_id ON chunks (workspace_id)")

    for table in TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            "USING (workspace_id = app_current_workspace()) "
            "WITH CHECK (workspace_id = app_current_workspace())"
        )
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {', '.join(TABLES)} TO {APP_ROLE}")


def downgrade() -> None:
    op.execute(
        "ALTER TABLE documents DROP CONSTRAINT IF EXISTS fk_documents_current_version_id_document_versions"
    )
    op.execute(
        "ALTER TABLE documents DROP CONSTRAINT IF EXISTS fk_documents_latest_version_id_document_versions"
    )
    for table in ("chunks", "document_pages", "document_versions", "documents"):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
    op.execute("DROP TYPE IF EXISTS document_status")
