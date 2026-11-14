"""Initial schema: identity, tenancy, audit, outbox, job queue, row-level security.

Revision ID: 0001
Revises:
Create Date: 2026-11-14

Extensions (citext, vector, pg_trgm) are created by infra/postgres/init as superuser.
The application connects as `citebase_app`, which does not own these tables and is subject
to FORCE ROW LEVEL SECURITY on every tenant table.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "citebase_app"
TENANT_TABLES = ("collections", "domain_events")


def _tenant_policy(table: str, column: str = "workspace_id") -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation ON {table} "
        f"USING ({column} = app_current_workspace()) "
        f"WITH CHECK ({column} = app_current_workspace())"
    )


def upgrade() -> None:
    # --- tenant context helpers ----------------------------------------------------------
    op.execute(
        """
        CREATE FUNCTION app_current_workspace() RETURNS uuid
        LANGUAGE sql STABLE AS
        $$ SELECT NULLIF(current_setting('app.workspace_id', true), '')::uuid $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION app_current_user() RETURNS uuid
        LANGUAGE sql STABLE AS
        $$ SELECT NULLIF(current_setting('app.user_id', true), '')::uuid $$
        """
    )

    # --- enums ---------------------------------------------------------------------------
    op.execute("CREATE TYPE token_purpose AS ENUM ('verify_email', 'reset_password')")
    op.execute("CREATE TYPE member_role AS ENUM ('owner', 'admin', 'member', 'viewer')")
    op.execute(
        "CREATE TYPE job_status AS ENUM ('queued', 'running', 'succeeded', 'failed', 'cancelled')"
    )

    # --- identity (global, no RLS) -------------------------------------------------------
    op.execute(
        """
        CREATE TABLE users (
            id uuid CONSTRAINT pk_users PRIMARY KEY,
            email citext NOT NULL CONSTRAINT uq_users_email UNIQUE,
            password_hash text NOT NULL,
            full_name varchar(120) NOT NULL,
            email_verified_at timestamptz,
            is_active boolean NOT NULL DEFAULT true,
            last_login_at timestamptz,
            deleted_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE auth_sessions (
            id uuid CONSTRAINT pk_auth_sessions PRIMARY KEY,
            user_id uuid NOT NULL
                CONSTRAINT fk_auth_sessions_user_id_users REFERENCES users(id) ON DELETE CASCADE,
            workspace_id uuid NOT NULL,
            family_id uuid NOT NULL,
            token_hash varchar(64) NOT NULL CONSTRAINT uq_auth_sessions_token_hash UNIQUE,
            expires_at timestamptz NOT NULL,
            revoked_at timestamptz,
            replaced_by_id uuid,
            rotated_at timestamptz,
            user_agent varchar(300),
            ip_hash varchar(64),
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX ix_auth_sessions_user_id ON auth_sessions (user_id)")
    op.execute("CREATE INDEX ix_auth_sessions_family_id ON auth_sessions (family_id)")
    op.execute(
        """
        CREATE TABLE auth_tokens (
            id uuid CONSTRAINT pk_auth_tokens PRIMARY KEY,
            user_id uuid NOT NULL
                CONSTRAINT fk_auth_tokens_user_id_users REFERENCES users(id) ON DELETE CASCADE,
            purpose token_purpose NOT NULL,
            token_hash varchar(64) NOT NULL CONSTRAINT uq_auth_tokens_token_hash UNIQUE,
            expires_at timestamptz NOT NULL,
            used_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX ix_auth_tokens_user_id ON auth_tokens (user_id)")

    # --- tenancy -------------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE workspaces (
            id uuid CONSTRAINT pk_workspaces PRIMARY KEY,
            name varchar(120) NOT NULL,
            slug varchar(80) NOT NULL CONSTRAINT uq_workspaces_slug UNIQUE,
            fts_config varchar(40) NOT NULL DEFAULT 'english',
            settings jsonb NOT NULL DEFAULT '{}'::jsonb,
            monthly_token_limit integer,
            max_documents integer NOT NULL DEFAULT 200,
            max_file_mb integer NOT NULL DEFAULT 25,
            deleted_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE memberships (
            id uuid CONSTRAINT pk_memberships PRIMARY KEY,
            workspace_id uuid NOT NULL
                CONSTRAINT fk_memberships_workspace_id_workspaces
                REFERENCES workspaces(id) ON DELETE CASCADE,
            user_id uuid NOT NULL
                CONSTRAINT fk_memberships_user_id_users REFERENCES users(id) ON DELETE CASCADE,
            role member_role NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_memberships_workspace_user UNIQUE (workspace_id, user_id)
        )
        """
    )
    op.execute("CREATE INDEX ix_memberships_user_id ON memberships (user_id)")
    op.execute(
        """
        CREATE TABLE collections (
            id uuid CONSTRAINT pk_collections PRIMARY KEY,
            workspace_id uuid NOT NULL
                CONSTRAINT fk_collections_workspace_id_workspaces
                REFERENCES workspaces(id) ON DELETE CASCADE,
            name varchar(120) NOT NULL,
            description text,
            is_default boolean NOT NULL DEFAULT false,
            deleted_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_collections_workspace_name_live "
        "ON collections (workspace_id, name) WHERE deleted_at IS NULL"
    )

    # --- audit, outbox, jobs -------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE audit_log (
            id uuid CONSTRAINT pk_audit_log PRIMARY KEY,
            workspace_id uuid,
            actor_user_id uuid,
            action varchar(80) NOT NULL,
            target_type varchar(40),
            target_id varchar(64),
            ip_hash varchar(64),
            details jsonb NOT NULL DEFAULT '{}'::jsonb,
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_audit_log_workspace_created ON audit_log (workspace_id, created_at)"
    )
    op.execute(
        """
        CREATE TABLE domain_events (
            id uuid CONSTRAINT pk_domain_events PRIMARY KEY,
            workspace_id uuid NOT NULL,
            event_type varchar(80) NOT NULL,
            payload jsonb NOT NULL,
            occurred_at timestamptz NOT NULL DEFAULT now(),
            dispatched_at timestamptz
        )
        """
    )
    op.execute("CREATE INDEX ix_domain_events_workspace_id ON domain_events (workspace_id)")
    op.execute(
        "CREATE INDEX ix_domain_events_undispatched ON domain_events (occurred_at) "
        "WHERE dispatched_at IS NULL"
    )
    op.execute(
        """
        CREATE TABLE jobs (
            id uuid CONSTRAINT pk_jobs PRIMARY KEY,
            workspace_id uuid,
            job_type varchar(40) NOT NULL,
            status job_status NOT NULL DEFAULT 'queued',
            payload jsonb NOT NULL DEFAULT '{}'::jsonb,
            attempts integer NOT NULL DEFAULT 0,
            max_attempts integer NOT NULL DEFAULT 5,
            run_after timestamptz NOT NULL DEFAULT now(),
            locked_by varchar(80),
            locked_at timestamptz,
            heartbeat_at timestamptz,
            last_error text,
            created_at timestamptz NOT NULL DEFAULT now(),
            finished_at timestamptz
        )
        """
    )
    op.execute("CREATE INDEX ix_jobs_workspace_id ON jobs (workspace_id)")
    op.execute("CREATE INDEX ix_jobs_claimable ON jobs (run_after) WHERE status = 'queued'")

    # --- row-level security --------------------------------------------------------------
    for table in TENANT_TABLES:
        _tenant_policy(table)

    _tenant_policy("workspaces", column="id")
    op.execute(
        "CREATE POLICY member_workspaces ON workspaces FOR SELECT USING ("
        "id IN (SELECT m.workspace_id FROM memberships m WHERE m.user_id = app_current_user()))"
    )

    _tenant_policy("memberships")
    op.execute(
        "CREATE POLICY own_memberships ON memberships FOR SELECT "
        "USING (user_id = app_current_user())"
    )

    op.execute("ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE audit_log FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_read ON audit_log FOR SELECT "
        "USING (workspace_id = app_current_workspace())"
    )
    op.execute(
        "CREATE POLICY tenant_insert ON audit_log FOR INSERT "
        "WITH CHECK (workspace_id IS NULL OR workspace_id = app_current_workspace())"
    )

    # --- grants for the application role -------------------------------------------------
    op.execute(f"GRANT USAGE ON SCHEMA public TO {APP_ROLE}")
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON users, auth_sessions, auth_tokens, workspaces, "
        f"memberships, collections, domain_events, jobs TO {APP_ROLE}"
    )
    op.execute(f"GRANT SELECT, INSERT ON audit_log TO {APP_ROLE}")  # append-only
    op.execute(
        f"GRANT EXECUTE ON FUNCTION app_current_workspace(), app_current_user() TO {APP_ROLE}"
    )


def downgrade() -> None:
    for table in (
        "jobs",
        "domain_events",
        "audit_log",
        "collections",
        "memberships",
        "workspaces",
        "auth_tokens",
        "auth_sessions",
        "users",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
    op.execute("DROP TYPE IF EXISTS job_status")
    op.execute("DROP TYPE IF EXISTS member_role")
    op.execute("DROP TYPE IF EXISTS token_purpose")
    op.execute("DROP FUNCTION IF EXISTS app_current_user()")
    op.execute("DROP FUNCTION IF EXISTS app_current_workspace()")
