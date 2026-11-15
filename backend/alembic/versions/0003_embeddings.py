"""Embeddings: profile catalog, per-profile chunk vectors with partial HNSW indexes, RLS.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-15

Each profile gets its own partial HNSW index over `embedding::vector(<dim>)`, so vectors of
different models never share an index and a workspace can switch models by re-embedding into
new rows. Seed rows mirror app/rag/profiles.py (a test checks they match).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "citebase_app"
# (id, key, provider, model, dimension, max_input_tokens)
PROFILES = [
    (1, "local-e5-small", "local", "intfloat/multilingual-e5-small", 384, 512),
    (2, "gemini-embedding-2-768", "gemini", "gemini-embedding-2", 768, 8192),
    (3, "openai-3-small", "openai", "text-embedding-3-small", 1536, 8191),
]


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE embedding_profiles (
            id smallint CONSTRAINT pk_embedding_profiles PRIMARY KEY,
            key varchar(60) NOT NULL CONSTRAINT uq_embedding_profiles_key UNIQUE,
            provider varchar(20) NOT NULL,
            model varchar(120) NOT NULL,
            dimension integer NOT NULL,
            max_input_tokens integer NOT NULL,
            is_active boolean NOT NULL DEFAULT true,
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    for pid, key, provider, model, dim, max_in in PROFILES:
        op.execute(
            "INSERT INTO embedding_profiles (id, key, provider, model, dimension, max_input_tokens) "  # noqa: S608 - seed constants
            f"VALUES ({pid}, '{key}', '{provider}', '{model}', {dim}, {max_in})"
        )

    op.execute(
        "ALTER TABLE workspaces ADD COLUMN embedding_profile_id smallint NOT NULL DEFAULT 2 "
        "CONSTRAINT fk_workspaces_embedding_profile_id_embedding_profiles "
        "REFERENCES embedding_profiles(id)"
    )
    op.execute(
        "ALTER TABLE document_versions ADD COLUMN embedding_profile_id smallint "
        "CONSTRAINT fk_document_versions_embedding_profile_id_embedding_profiles "
        "REFERENCES embedding_profiles(id)"
    )

    op.execute(
        """
        CREATE TABLE chunk_embeddings (
            chunk_id uuid NOT NULL
                CONSTRAINT fk_chunk_embeddings_chunk_id_chunks
                REFERENCES chunks(id) ON DELETE CASCADE,
            profile_id smallint NOT NULL
                CONSTRAINT fk_chunk_embeddings_profile_id_embedding_profiles
                REFERENCES embedding_profiles(id),
            workspace_id uuid NOT NULL,
            content_hash varchar(64) NOT NULL,
            embedding vector NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT pk_chunk_embeddings PRIMARY KEY (chunk_id, profile_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_chunk_embeddings_cache "
        "ON chunk_embeddings (workspace_id, profile_id, content_hash)"
    )
    for pid, _key, _provider, _model, dim, _max in PROFILES:
        op.execute(
            f"CREATE INDEX ix_chunk_embeddings_hnsw_p{pid} ON chunk_embeddings "
            f"USING hnsw ((embedding::vector({dim})) vector_cosine_ops) "
            f"WHERE profile_id = {pid}"
        )

    op.execute("ALTER TABLE chunk_embeddings ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE chunk_embeddings FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON chunk_embeddings "
        "USING (workspace_id = app_current_workspace()) "
        "WITH CHECK (workspace_id = app_current_workspace())"
    )
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON chunk_embeddings TO {APP_ROLE}")
    op.execute(f"GRANT SELECT ON embedding_profiles TO {APP_ROLE}")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS chunk_embeddings CASCADE")
    op.execute("ALTER TABLE document_versions DROP COLUMN IF EXISTS embedding_profile_id")
    op.execute("ALTER TABLE workspaces DROP COLUMN IF EXISTS embedding_profile_id")
    op.execute("DROP TABLE IF EXISTS embedding_profiles CASCADE")
