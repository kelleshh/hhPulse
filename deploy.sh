#!/usr/bin/env bash

set -Eeuo pipefail

readonly PROJECT_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly ENV_FILE="${PROJECT_DIR}/.env"
readonly ENV_EXAMPLE="${PROJECT_DIR}/.env.example"
readonly DEFAULT_TIMEOUT_SECONDS=180

cd "${PROJECT_DIR}"

compose() {
  docker compose "$@"
}

die() {
  printf 'Ошибка: %s\n' "$*" >&2
  exit 1
}

read_env_value() {
  local key="$1"
  local fallback="$2"
  local value=""

  if [[ -f "${ENV_FILE}" ]]; then
    value="$(sed -n "s/^${key}=//p" "${ENV_FILE}" | tail -n 1)"
    value="${value%\"}"
    value="${value#\"}"
  fi
  printf '%s' "${value:-${fallback}}"
}

require_runtime() {
  command -v docker >/dev/null 2>&1 || die "Docker не установлен."
  docker info >/dev/null 2>&1 || die "Docker daemon не запущен или текущему пользователю запрещён доступ."
  docker compose version >/dev/null 2>&1 || die "Не установлен плагин Docker Compose v2."
}

ensure_env() {
  if [[ -f "${ENV_FILE}" ]]; then
    return
  fi
  [[ -f "${ENV_EXAMPLE}" ]] || die "Не найден ${ENV_EXAMPLE}."
  cp "${ENV_EXAMPLE}" "${ENV_FILE}"
  printf 'Создан .env из безопасных локальных настроек по умолчанию.\n'
}

service_state() {
  local service="$1"
  local container_id
  container_id="$(compose ps -q "${service}")"
  if [[ -z "${container_id}" ]]; then
    printf 'missing'
    return
  fi
  docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "${container_id}" 2>/dev/null || printf 'missing'
}

wait_for_service() {
  local service="$1"
  local timeout_seconds="$2"
  local started_at now state
  started_at="$(date +%s)"

  printf 'Ожидаю готовность %s' "${service}"
  while true; do
    state="$(service_state "${service}")"
    case "${state}" in
      healthy|running)
        printf ' — готово.\n'
        return
        ;;
      unhealthy|exited|dead)
        printf ' — %s.\n' "${state}"
        compose logs --tail=120 "${service}" >&2
        die "Сервис ${service} не запустился."
        ;;
    esac

    now="$(date +%s)"
    if (( now - started_at >= timeout_seconds )); then
      printf ' — превышен таймаут.\n'
      compose logs --tail=120 "${service}" >&2
      die "Сервис ${service} не стал готов за ${timeout_seconds} секунд."
    fi
    printf '.'
    sleep 2
  done
}

web_url() {
  local published port
  published="$(compose port frontend 8080 2>/dev/null | tail -n 1)"
  port="${published##*:}"
  printf 'http://localhost:%s' "${port:-$(read_env_value HHPULSE_WEB_PORT 3000)}"
}

open_browser() {
  local url="$1"
  local enabled
  enabled="$(read_env_value HHPULSE_OPEN_BROWSER 1)"
  if [[ "${enabled}" == "1" && -n "${DISPLAY:-}" ]] && command -v xdg-open >/dev/null 2>&1; then
    xdg-open "${url}" >/dev/null 2>&1 &
  fi
}

deployment_timeout() {
  local value
  value="$(read_env_value HHPULSE_DEPLOY_TIMEOUT_SECONDS "${DEFAULT_TIMEOUT_SECONDS}")"
  [[ "${value}" =~ ^[1-9][0-9]*$ ]] || die "HHPULSE_DEPLOY_TIMEOUT_SECONDS должен быть целым числом больше нуля."
  printf '%s' "${value}"
}

show_success() {
  local url
  url="$(web_url)"
  printf '\nhhPulse запущен.\n'
  printf 'Интерфейс: %s\n' "${url}"
  printf 'Документация API: %s/docs\n\n' "${url}"
  compose ps
  open_browser "${url}"
}

deploy() {
  local timeout_seconds
  timeout_seconds="$(deployment_timeout)"
  export DOCKER_BUILDKIT=1

  compose config --quiet
  printf 'Собираю и запускаю hhPulse. Повторная сборка использует кэш.\n'
  compose up --detach --build --remove-orphans
  wait_for_service api "${timeout_seconds}"
  wait_for_service frontend "${timeout_seconds}"
  show_success
}

update() {
  local timeout_seconds
  timeout_seconds="$(deployment_timeout)"
  export DOCKER_BUILDKIT=1
  compose config --quiet
  printf 'Обновляю базовые образы и пересобираю hhPulse.\n'
  compose build --pull
  compose up --detach --remove-orphans
  wait_for_service api "${timeout_seconds}"
  wait_for_service frontend "${timeout_seconds}"
  show_success
}

doctor() {
  compose config --quiet
  printf 'Docker: '
  docker version --format '{{.Server.Version}}'
  printf 'Compose: '
  docker compose version --short
  printf 'Конфигурация корректна.\n'
  compose ps
}

usage() {
  cat <<'EOF'
Использование:
  ./deploy.sh           собрать, запустить и открыть hhPulse
  ./deploy.sh update    обновить базовые образы и пересобрать
  ./deploy.sh status    показать состояние контейнеров
  ./deploy.sh logs      следить за логами
  ./deploy.sh restart   перезапустить без пересборки
  ./deploy.sh stop      остановить, сохранив данные
  ./deploy.sh down      удалить контейнеры и сеть, сохранив volume с данными
  ./deploy.sh doctor    проверить Docker и Compose-конфигурацию
EOF
}

main() {
  local command="${1:-deploy}"

  case "${command}" in
    help|-h|--help) usage; return ;;
  esac

  require_runtime
  ensure_env

  case "${command}" in
    deploy) deploy ;;
    update) update ;;
    status) compose ps ;;
    logs) compose logs --follow --tail=200 api frontend ;;
    restart)
      compose restart
      wait_for_service api "$(deployment_timeout)"
      wait_for_service frontend "$(deployment_timeout)"
      show_success
      ;;
    stop) compose stop ;;
    down) compose down --remove-orphans ;;
    doctor) doctor ;;
    *) usage; die "Неизвестная команда: ${command}" ;;
  esac
}

main "$@"
