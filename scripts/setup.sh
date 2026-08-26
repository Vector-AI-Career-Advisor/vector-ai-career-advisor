#!/usr/bin/env bash
# One-time (and safe-to-rerun) environment setup:
#   Postgres up -> app database -> tables (via the API's own init_db()) ->
#   vector_agent role -> full docker-compose stack -> frontend deps.
#
# Run from the repo root: ./scripts/setup.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/.."
cd "$ROOT"

if [ ! -f .env ]; then
  echo "Missing .env — copy .env.example to .env and fill it in first." >&2
  exit 1
fi

DB_NAME="$(grep -E '^DB_NAME=' .env | cut -d= -f2-)"
AGENT_DB_PASSWORD="$(grep -E '^AGENT_DB_PASSWORD=' .env | cut -d= -f2-)"

if [ -z "$DB_NAME" ] || [ -z "$AGENT_DB_PASSWORD" ]; then
  echo "DB_NAME and AGENT_DB_PASSWORD must both be set in .env." >&2
  exit 1
fi

echo "==> Building images"
docker compose build

echo "==> Starting Postgres"
docker compose up -d postgres
echo "    waiting for it to be healthy..."
until [ "$(docker compose ps -q postgres | xargs docker inspect -f '{{.State.Health.Status}}')" = "healthy" ]; do
  sleep 1
done

echo "==> Creating database '$DB_NAME' (no-op if it already exists)"
docker compose exec postgres psql -U postgres -tc \
  "SELECT 1 FROM pg_database WHERE datname = '$DB_NAME'" | grep -q 1 \
  || docker compose exec postgres psql -U postgres -c "CREATE DATABASE $DB_NAME;"

echo "==> Creating tables (runs the API's own init_db(), skipping mcp-db so it"
echo "    doesn't crash-loop before the vector_agent role exists below)"
docker compose run --rm --no-deps --workdir /app server python -c "from server.db.postgres import init_db; init_db()"

echo "==> Creating the read-only vector_agent role"
docker compose exec -T postgres psql -U postgres -d "$DB_NAME" \
  -v dbname="$DB_NAME" \
  -v agent_pw="$AGENT_DB_PASSWORD" \
  < scripts/sql/create_agent_role.sql

echo "==> Starting the full stack"
docker compose up -d

echo "==> Installing frontend dependencies"
(cd client && npm install)

cat <<'EOF'

Done.
  API:      http://localhost:8000
  Airflow:  http://localhost:8080
  Frontend: cd client && npm run dev   (serves on http://localhost:5173)
EOF
