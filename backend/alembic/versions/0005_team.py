"""Team invitations; trigram index for conversation search.

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-17

Invitations are tenant rows (RLS by workspace). Someone opening an invite link has no tenant
context yet, so `app_invitation_workspace(token_hash)` resolves only the workspace id for one
exact token hash. It is SECURITY DEFINER and owned by the table owner; the table has RLS ENABLED
but not FORCED so that this one function can read it, while the application role (not the owner)
stays fully subject to the tenant policy. The caller then sets the tenant and reads the row under RLS.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "citebase_app"


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE invitations (
            id uuid CONSTRAINT pk_invitations PRIMARY KEY,
            workspace_id uuid NOT NULL
                CONSTRAINT fk_invitations_workspace_id_workspaces
                REFERENCES workspaces(id) ON DELETE CASCADE,
            email citext NOT NULL,
            role member_role NOT NULL CONSTRAINT ck_invitations_not_owner CHECK (role <> 'owner'),
            token_hash varchar(64) NOT NULL CONSTRAINT uq_invitations_token_hash UNIQUE,
            invited_by_id uuid
                CONSTRAINT fk_invitations_invited_by_id_users
                REFERENCES users(id) ON DELETE SET NULL,
            expires_at timestamptz NOT NULL,
            accepted_at timestamptz,
            revoked_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX ix_invitations_workspace_id ON invitations (workspace_id)")
    op.execute("ALTER TABLE invitations ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON invitations "
        "USING (workspace_id = app_current_workspace()) "
        "WITH CHECK (workspace_id = app_current_workspace())"
    )
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON invitations TO {APP_ROLE}")
    op.execute(
        """
        CREATE FUNCTION app_invitation_workspace(p_token_hash text) RETURNS uuid
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS
        $$ SELECT workspace_id FROM invitations WHERE token_hash = p_token_hash $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION app_invitation_workspace(text) FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION app_invitation_workspace(text) TO {APP_ROLE}")

    op.execute(
        "CREATE INDEX ix_conversations_title_trgm ON conversations USING gin (title gin_trgm_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_conversations_title_trgm")
    op.execute("DROP FUNCTION IF EXISTS app_invitation_workspace(text)")
    op.execute("DROP TABLE IF EXISTS invitations CASCADE")
