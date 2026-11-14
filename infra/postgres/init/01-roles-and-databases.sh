#!/usr/bin/env bash
# Creates the owner and application roles, the app and test databases, and extensions.
# Runs automatically on first start of the Postgres container (docker-entrypoint-initdb.d).
# CI runs it directly with PGHOST/PGUSER/PGPASSWORD set.
set -euo pipefail

: "${CITEBASE_OWNER_PASSWORD:?CITEBASE_OWNER_PASSWORD is required}"
: "${CITEBASE_APP_PASSWORD:?CITEBASE_APP_PASSWORD is required}"
PGUSER="${PGUSER:-${POSTGRES_USER:-postgres}}"
export PGUSER

psql -v ON_ERROR_STOP=1 --dbname postgres \
  -v owner_pw="$CITEBASE_OWNER_PASSWORD" -v app_pw="$CITEBASE_APP_PASSWORD" <<'SQL'
CREATE ROLE citebase_owner LOGIN PASSWORD :'owner_pw';
CREATE ROLE citebase_app LOGIN PASSWORD :'app_pw' NOSUPERUSER NOBYPASSRLS;
CREATE DATABASE citebase OWNER citebase_owner;
CREATE DATABASE citebase_test OWNER citebase_owner;
SQL

for db in citebase citebase_test; do
  psql -v ON_ERROR_STOP=1 --dbname "$db" <<SQL
CREATE EXTENSION IF NOT EXISTS citext;
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
REVOKE ALL ON DATABASE $db FROM PUBLIC;
GRANT CONNECT ON DATABASE $db TO citebase_app;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO citebase_app;
SQL
done

echo "citebase roles, databases and extensions are ready"
