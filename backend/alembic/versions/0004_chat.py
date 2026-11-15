"""Chat: conversations, messages, message sources, feedback, unanswered questions, usage. RLS.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-16

message_sources keeps a snapshot (title, location, snippet) of every passage shown to the model,
so old answers still render after a document changes. Purging a document blanks those snippets
(see repositories/documents.delete_document); the foreign keys then become NULL.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "citebase_app"
TABLES = (
    "conversations",
    "messages",
    "message_sources",
    "feedback",
    "unanswered_questions",
    "usage_events",
)
ENUMS = {
    "message_role": ("user", "assistant"),
    "message_status": ("streaming", "complete", "stopped", "refused", "error"),
    "refusal_reason": ("gate", "model", "no_valid_citation"),
    "evidence_strength": ("strong", "partial", "weak"),
    "feedback_rating": ("helpful", "not_helpful"),
    "unanswered_status": ("open", "resolved", "dismissed"),
    "usage_kind": ("chat", "rewrite", "regenerate", "suggest"),
}


def upgrade() -> None:
    for name, values in ENUMS.items():
        labels = ", ".join(f"'{v}'" for v in values)
        op.execute(f"CREATE TYPE {name} AS ENUM ({labels})")

    op.execute(
        """
        CREATE TABLE conversations (
            id uuid CONSTRAINT pk_conversations PRIMARY KEY,
            workspace_id uuid NOT NULL
                CONSTRAINT fk_conversations_workspace_id_workspaces
                REFERENCES workspaces(id) ON DELETE CASCADE,
            user_id uuid NOT NULL
                CONSTRAINT fk_conversations_user_id_users REFERENCES users(id) ON DELETE CASCADE,
            title varchar(200) NOT NULL,
            deleted_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_conversations_owner ON conversations (workspace_id, user_id, updated_at)"
    )

    op.execute(
        """
        CREATE TABLE messages (
            id uuid CONSTRAINT pk_messages PRIMARY KEY,
            workspace_id uuid NOT NULL,
            conversation_id uuid NOT NULL
                CONSTRAINT fk_messages_conversation_id_conversations
                REFERENCES conversations(id) ON DELETE CASCADE,
            role message_role NOT NULL,
            content text NOT NULL DEFAULT '',
            standalone_query text,
            status message_status NOT NULL,
            refusal_reason refusal_reason,
            evidence_strength evidence_strength,
            prompt_version varchar(40),
            llm_provider varchar(40),
            llm_model varchar(120),
            input_tokens integer,
            output_tokens integer,
            latency_ms integer,
            retrieval_trace jsonb,
            regenerated_from_id uuid
                CONSTRAINT fk_messages_regenerated_from_id_messages
                REFERENCES messages(id) ON DELETE SET NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX ix_messages_thread ON messages (conversation_id, created_at)")
    op.execute("CREATE INDEX ix_messages_workspace_created ON messages (workspace_id, created_at)")

    op.execute(
        """
        CREATE TABLE message_sources (
            id uuid CONSTRAINT pk_message_sources PRIMARY KEY,
            workspace_id uuid NOT NULL,
            message_id uuid NOT NULL
                CONSTRAINT fk_message_sources_message_id_messages
                REFERENCES messages(id) ON DELETE CASCADE,
            source_number smallint NOT NULL,
            chunk_id uuid
                CONSTRAINT fk_message_sources_chunk_id_chunks
                REFERENCES chunks(id) ON DELETE SET NULL,
            document_id uuid
                CONSTRAINT fk_message_sources_document_id_documents
                REFERENCES documents(id) ON DELETE SET NULL,
            document_version_id uuid,
            document_title varchar(255) NOT NULL,
            section_title text,
            location varchar(200) NOT NULL,
            page_start integer NOT NULL,
            page_end integer NOT NULL,
            snippet text NOT NULL,
            vector_score double precision,
            keyword_score double precision,
            fused_score double precision NOT NULL,
            cited boolean NOT NULL DEFAULT false,
            CONSTRAINT uq_message_sources_message_id UNIQUE (message_id, source_number)
        )
        """
    )
    op.execute("CREATE INDEX ix_message_sources_document_id ON message_sources (document_id)")

    op.execute(
        """
        CREATE TABLE feedback (
            id uuid CONSTRAINT pk_feedback PRIMARY KEY,
            workspace_id uuid NOT NULL,
            message_id uuid NOT NULL
                CONSTRAINT fk_feedback_message_id_messages
                REFERENCES messages(id) ON DELETE CASCADE,
            user_id uuid NOT NULL
                CONSTRAINT fk_feedback_user_id_users REFERENCES users(id) ON DELETE CASCADE,
            rating feedback_rating NOT NULL,
            comment text,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_feedback_message_id UNIQUE (message_id, user_id)
        )
        """
    )
    op.execute("CREATE INDEX ix_feedback_workspace_id ON feedback (workspace_id)")

    op.execute(
        """
        CREATE TABLE unanswered_questions (
            id uuid CONSTRAINT pk_unanswered_questions PRIMARY KEY,
            workspace_id uuid NOT NULL,
            message_id uuid NOT NULL
                CONSTRAINT fk_unanswered_questions_message_id_messages
                REFERENCES messages(id) ON DELETE CASCADE
                CONSTRAINT uq_unanswered_questions_message_id UNIQUE,
            user_id uuid
                CONSTRAINT fk_unanswered_questions_user_id_users
                REFERENCES users(id) ON DELETE SET NULL,
            question text NOT NULL,
            reason refusal_reason NOT NULL,
            status unanswered_status NOT NULL DEFAULT 'open',
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_unanswered_questions_queue "
        "ON unanswered_questions (workspace_id, status, created_at)"
    )

    op.execute(
        """
        CREATE TABLE usage_events (
            id uuid CONSTRAINT pk_usage_events PRIMARY KEY,
            workspace_id uuid NOT NULL,
            user_id uuid
                CONSTRAINT fk_usage_events_user_id_users REFERENCES users(id) ON DELETE SET NULL,
            message_id uuid
                CONSTRAINT fk_usage_events_message_id_messages
                REFERENCES messages(id) ON DELETE SET NULL,
            kind usage_kind NOT NULL,
            provider varchar(40) NOT NULL,
            model varchar(120) NOT NULL,
            input_tokens integer NOT NULL DEFAULT 0,
            output_tokens integer NOT NULL DEFAULT 0,
            estimated boolean NOT NULL DEFAULT false,
            cost_usd numeric(12, 6),
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_usage_events_workspace_created ON usage_events (workspace_id, created_at)"
    )

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
    for table in reversed(TABLES):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
    for name in ENUMS:
        op.execute(f"DROP TYPE IF EXISTS {name}")
