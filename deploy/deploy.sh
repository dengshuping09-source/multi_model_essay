#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${WENHENG_ENV_FILE:-${SCRIPT_DIR}/production.env}"
COMPOSE_FILE="${PROJECT_DIR}/compose.production.yaml"
DEPLOY_BRANCH="${DEPLOY_BRANCH:-main}"

cd "${PROJECT_DIR}"

if [[ ! -f "${ENV_FILE}" ]]; then
    echo "Missing production environment file: ${ENV_FILE}" >&2
    echo "Create it from deploy/production.env.example and keep it outside Git." >&2
    exit 1
fi

chmod 600 "${ENV_FILE}"

env_value() {
    local key="$1"
    awk -F= -v key="${key}" '$1 == key {print substr($0, index($0, "=") + 1)}' "${ENV_FILE}" \
        | tail -n 1 \
        | tr -d '\r'
}

require_production_value() {
    local key="$1"
    local value
    value="$(env_value "${key}")"
    if [[ -z "${value}" || "${value}" == *replace_with* ]]; then
        echo "${key} is not configured with a production value in ${ENV_FILE}." >&2
        exit 1
    fi
}

database_url="$(env_value DATABASE_URL)"
if [[ -z "${database_url}" || "${database_url}" == *database-host* || "${database_url}" == *URL_ENCODED_PASSWORD* ]]; then
    echo "DATABASE_URL is not configured with a production connection in ${ENV_FILE}." >&2
    exit 1
fi

require_production_value DEEPSEEK_API_KEY
require_production_value QWEN_API_KEY
require_production_value ARK_API_KEY

backup_confirmed="$(env_value DATABASE_MIGRATION_BACKUP_CONFIRMED)"
if [[ "${backup_confirmed}" != "yes" ]]; then
    echo "Database migration stopped: confirm a current backup or snapshot first." >&2
    echo "Then set DATABASE_MIGRATION_BACKUP_CONFIRMED=yes in ${ENV_FILE}." >&2
    exit 1
fi

if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "Deployment stopped because the server working tree has local changes." >&2
    exit 1
fi

git fetch origin "${DEPLOY_BRANCH}"
git checkout "${DEPLOY_BRANCH}"
git merge --ff-only "origin/${DEPLOY_BRANCH}"

export WENHENG_ENV_FILE="${ENV_FILE}"
compose=(docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}")

"${compose[@]}" config --quiet
"${compose[@]}" build

# Check connectivity before any schema migration. This executes SELECT 1 only.
"${compose[@]}" run --rm backend python -c \
    'import asyncio; from app.db.session import check_database_connection; asyncio.run(check_database_connection())'

# Alembic upgrades the configured database in place. It does not create or
# delete a PostgreSQL server/database, and only runs after backup confirmation.
"${compose[@]}" run --rm backend python -m alembic upgrade head

"${compose[@]}" up -d --remove-orphans
"${compose[@]}" ps
"${compose[@]}" exec -T frontend wget -qO- http://127.0.0.1/healthz
echo
echo "Wenheng deployment is healthy on ${WEB_BIND_ADDRESS:-127.0.0.1}:${WEB_PORT:-18080}."
