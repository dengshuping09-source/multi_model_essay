#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${WENHENG_ENV_FILE:-${SCRIPT_DIR}/production.env}"
COMPOSE_FILE="${PROJECT_DIR}/compose.production.yaml"
OVERRIDE_FILE="${WENHENG_COMPOSE_OVERRIDE_FILE:-}"
DEPLOY_BRANCH="${DEPLOY_BRANCH:-main}"
DEPLOY_KEY="${WENHENG_DEPLOY_KEY:-}"
EXPECTED_COMMIT="${WENHENG_EXPECTED_COMMIT:-}"
SKIP_GIT_UPDATE="${WENHENG_SKIP_GIT_UPDATE:-0}"
STATE_DIR="${WENHENG_DEPLOY_STATE_DIR:-/opt/wenheng-secrets}"
LAST_DEPLOYED_FILE="${STATE_DIR}/last-deployed-commit"
BACKUP_ROOT="${WENHENG_BACKUP_ROOT:-/opt/backups/wenheng}"
LOCK_FILE="${WENHENG_DEPLOY_LOCK_FILE:-/tmp/wenheng-production-deploy.lock}"

cd "${PROJECT_DIR}"

if [[ "${WENHENG_LOCK_HELD:-0}" != "1" ]]; then
    exec 9>"${LOCK_FILE}"
    if ! flock -n 9; then
        echo "Another Wenheng deployment is already running." >&2
        exit 1
    fi
fi

if [[ ! -f "${ENV_FILE}" ]]; then
    echo "Missing production environment file: ${ENV_FILE}" >&2
    exit 1
fi

if [[ -n "${OVERRIDE_FILE}" && ! -f "${OVERRIDE_FILE}" ]]; then
    echo "Missing Compose override file: ${OVERRIDE_FILE}" >&2
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
    echo "Database migration stopped: DATABASE_MIGRATION_BACKUP_CONFIRMED must be yes." >&2
    exit 1
fi

if [[ -n "$(git status --porcelain)" ]]; then
    echo "Deployment stopped because the server working tree has local changes." >&2
    exit 1
fi

if [[ "${SKIP_GIT_UPDATE}" != "1" ]]; then
    if [[ -n "${DEPLOY_KEY}" ]]; then
        export GIT_SSH_COMMAND="ssh -i ${DEPLOY_KEY} -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes"
    fi
    git fetch origin "${DEPLOY_BRANCH}"
    remote_commit="$(git rev-parse "origin/${DEPLOY_BRANCH}")"
    if [[ -n "${EXPECTED_COMMIT}" && "${remote_commit}" != "${EXPECTED_COMMIT}" ]]; then
        echo "Deployment stopped: origin/${DEPLOY_BRANCH} does not match the requested commit." >&2
        exit 1
    fi
    git checkout "${DEPLOY_BRANCH}"
    git merge --ff-only "origin/${DEPLOY_BRANCH}"
fi

target_commit="$(git rev-parse HEAD)"
if [[ -n "${EXPECTED_COMMIT}" && "${target_commit}" != "${EXPECTED_COMMIT}" ]]; then
    echo "Deployment stopped: checked-out commit does not match the requested commit." >&2
    exit 1
fi

previous_commit=""
if [[ -f "${LAST_DEPLOYED_FILE}" ]]; then
    previous_commit="$(tr -d '\r\n' < "${LAST_DEPLOYED_FILE}")"
fi
if [[ -n "${previous_commit}" ]] && ! git cat-file -e "${previous_commit}^{commit}" 2>/dev/null; then
    echo "Ignoring invalid last-deployed marker and performing a full rebuild." >&2
    previous_commit=""
fi

if [[ "${EUID}" -eq 0 ]]; then
    compose=(env WENHENG_ENV_FILE="${ENV_FILE}" docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}")
    docker_cli=(docker)
    postgres_sudo=(sudo -n -u postgres)
    system_sudo=()
else
    compose=(sudo -n env WENHENG_ENV_FILE="${ENV_FILE}" docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}")
    docker_cli=(sudo -n docker)
    postgres_sudo=(sudo -n -u postgres)
    system_sudo=(sudo -n)
fi
if [[ -n "${OVERRIDE_FILE}" ]]; then
    compose+=( -f "${OVERRIDE_FILE}" )
fi

# Baidu is the normal production OCR path and does not need a separate model
# worker. Paddle remains an explicit fallback: enable both settings before a
# deployment when that worker is intentionally required.
ocr_default_engine="$(env_value OCR_DEFAULT_ENGINE)"
ocr_worker_enabled="$(env_value OCR_WORKER_ENABLED)"
paddle_worker_enabled=0
if [[ "${ocr_default_engine}" == "paddle" && "${ocr_worker_enabled}" == "true" ]]; then
    compose+=( --profile paddle-worker )
    paddle_worker_enabled=1
fi

"${compose[@]}" config --quiet
"${system_sudo[@]}" nginx -t

backend_changed=0
frontend_changed=0
if [[ -z "${previous_commit}" ]]; then
    backend_changed=1
    frontend_changed=1
elif [[ "${previous_commit}" != "${target_commit}" ]]; then
    changed_files="$(git diff --name-only "${previous_commit}" "${target_commit}")"
    if grep -Eq '^(backend/|compose\.production\.yaml$)' <<<"${changed_files}"; then
        backend_changed=1
    fi
    if grep -Eq '^(frontend/|compose\.production\.yaml$)' <<<"${changed_files}"; then
        frontend_changed=1
    fi
fi

if [[ "${WENHENG_FORCE_BACKEND:-0}" == "1" ]]; then
    backend_changed=1
fi
if [[ "${WENHENG_FORCE_FRONTEND:-0}" == "1" ]]; then
    frontend_changed=1
fi

previous_backend_image="$("${docker_cli[@]}" inspect -f '{{.Image}}' wenheng-backend-1 2>/dev/null || true)"
previous_ocr_worker_image=""
if [[ "${paddle_worker_enabled}" == "1" ]]; then
    previous_ocr_worker_image="$("${docker_cli[@]}" inspect -f '{{.Image}}' wenheng-ocr-worker-1 2>/dev/null || true)"
fi
legacy_ocr_worker_was_running="$("${docker_cli[@]}" inspect -f '{{.State.Running}}' wenheng-ocr-worker-1 2>/dev/null || true)"
previous_frontend_image="$("${docker_cli[@]}" inspect -f '{{.Image}}' wenheng-frontend-1 2>/dev/null || true)"
deployment_swapped=0

rollback_containers() {
    local exit_code=$?
    trap - ERR
    set +e
    if [[ "${deployment_swapped}" == "1" ]]; then
        echo "Deployment failed after container replacement; restoring previous application images." >&2
        rollback_services=()
        if [[ "${backend_changed}" == "1" && -n "${previous_backend_image}" ]]; then
            "${docker_cli[@]}" image tag "${previous_backend_image}" wenheng-backend:local
            rollback_services+=(backend)
            if [[ "${paddle_worker_enabled}" == "1" && -n "${previous_ocr_worker_image}" ]]; then
                rollback_services+=(ocr-worker)
            elif [[ "${paddle_worker_enabled}" == "1" ]]; then
                "${compose[@]}" stop ocr-worker >/dev/null 2>&1 || true
            fi
        fi
        if [[ "${frontend_changed}" == "1" && -n "${previous_frontend_image}" ]]; then
            "${docker_cli[@]}" image tag "${previous_frontend_image}" wenheng-frontend:local
            rollback_services+=(frontend)
        fi
        if (( ${#rollback_services[@]} > 0 )); then
            "${compose[@]}" up -d --force-recreate --no-deps "${rollback_services[@]}"
        fi
        if [[ "${paddle_worker_enabled}" != "1" && "${legacy_ocr_worker_was_running}" == "true" ]]; then
            "${docker_cli[@]}" start wenheng-ocr-worker-1 >/dev/null 2>&1 || true
        fi
    fi
    echo "DEPLOYMENT_FAILED commit=${target_commit}" >&2
    exit "${exit_code}"
}
trap rollback_containers ERR

services_to_update=()
if [[ "${backend_changed}" == "1" ]]; then
    echo "Building backend image; unchanged requirements reuse the Docker dependency layer."
    "${compose[@]}" build backend
    services_to_update+=(backend)
    if [[ "${paddle_worker_enabled}" == "1" ]]; then
        services_to_update+=(ocr-worker)
    fi
fi
if [[ "${frontend_changed}" == "1" ]]; then
    echo "Building frontend image; unchanged package lock files reuse the npm dependency layer."
    "${compose[@]}" build frontend
    services_to_update+=(frontend)
fi

if [[ "${backend_changed}" == "1" && "${paddle_worker_enabled}" == "1" ]]; then
    "${compose[@]}" run --rm --no-deps -T backend python -c \
        'import asyncio; from app.db.session import check_database_connection; asyncio.run(check_database_connection())'

    timestamp="$(date +%Y%m%d-%H%M%S)"
    backup_dir="${BACKUP_ROOT}/${timestamp}"
    "${system_sudo[@]}" install -d -m 700 -o postgres -g postgres "${backup_dir}"
    "${postgres_sudo[@]}" pg_dump --format=custom --file="${backup_dir}/essay_evaluation.dump" essay_evaluation
    "${postgres_sudo[@]}" pg_restore --list "${backup_dir}/essay_evaluation.dump" >/dev/null
    echo "Database backup verified: ${backup_dir}/essay_evaluation.dump"

    "${compose[@]}" run --rm --no-deps -T backend python -m alembic upgrade head
fi

if (( ${#services_to_update[@]} > 0 )); then
    deployment_swapped=1
    "${compose[@]}" up -d --no-deps "${services_to_update[@]}"
else
    echo "No frontend or backend source changes detected; keeping current containers."
fi

if [[ "${backend_changed}" == "1" ]]; then
    for attempt in $(seq 1 15); do
        worker_running="$("${docker_cli[@]}" inspect -f '{{.State.Running}}' wenheng-ocr-worker-1 2>/dev/null || true)"
        if [[ "${worker_running}" == "true" ]]; then
            break
        fi
        if [[ "${attempt}" == "15" ]]; then
            echo "OCR worker did not remain running after deployment." >&2
            false
        fi
        sleep 2
    done
fi

for attempt in $(seq 1 45); do
    if curl -fsS --max-time 5 http://127.0.0.1/api/health >/dev/null \
        && curl -fsS --max-time 5 http://127.0.0.1/ >/dev/null; then
        break
    fi
    if [[ "${attempt}" == "45" ]]; then
        echo "Application health checks did not pass within 90 seconds." >&2
        false
    fi
    sleep 2
done

if [[ "${paddle_worker_enabled}" != "1" && "${legacy_ocr_worker_was_running}" == "true" ]]; then
    echo "Stopping legacy Paddle OCR worker; Baidu OCR is the configured production provider."
    "${docker_cli[@]}" stop wenheng-ocr-worker-1 >/dev/null
fi

"${system_sudo[@]}" systemctl reload nginx
"${compose[@]}" ps
install -d -m 700 "${STATE_DIR}"
printf '%s\n' "${target_commit}" > "${LAST_DEPLOYED_FILE}"
chmod 600 "${LAST_DEPLOYED_FILE}"
trap - ERR
echo "DEPLOYMENT_OK commit=${target_commit}"
