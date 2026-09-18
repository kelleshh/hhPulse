# hhPulse — personal fork

Локальный сервис для ежедневного измерения конкуренции на рынке труда через агрегированные
счётчики поисковой выдачи hh.ru. В этой ветке **не скачиваются отдельные вакансии и резюме**:
источником фактов являются только уже рассчитанные hh.ru числа из HTML поисковых страниц.

## Что реализовано

- DDD/Clean Architecture: `domain -> application -> infrastructure -> api`.
- Доменные модели задач анализа, дневных прогонов, crawl-unit, HH-индекса и снимка рынка.
- Версионируемая методология `hh-index-daily-v1`: активные резюме за последние 60 календарных
  дней, вакансии — активные на день наблюдения.
- Динамическое получение полного каталога professional roles через официальный справочник
  `GET https://api.hh.ru/professional_roles`, без списка ID в коде. Facet `professional_role`
  используется только как метрика текущей выдачи и не может молча выкинуть роли с нулём вакансий.
- HTML parser, который извлекает:
  - общее число найденных вакансий/резюме;
  - весь `searchClusters` и его facet counts;
  - `professional_role` как обычный facet текущей выдачи, без использования его как полного каталога.
- Async HH transport на `httpx` с пользовательскими `max_concurrency` и `max_rps`.
- Адаптивный backoff: 429/502/503/504 только замедляют клиент; лимит пользователя никогда не
  превышается.
- Режим User-Agent: один на все worker-ы или детерминированный UA на worker.
- Persisted control-plane на SQLite/WAL: задачи, дневные run-ы, crawl-unit-ы.
- Staging/publish модель: частичный run можно сохранять и продолжать после рестарта, а в
  published history он попадает только целиком.
- FastAPI endpoints для создания, чтения, списка и включения/выключения задач.
- Исполняемое ядро второй итерации:
  - `PrepareOrResumeDailyRun` с тремя последовательными preflight-проверками;
  - атомарное создание persisted crawl units;
  - async worker pool с атомарным claim каждой единицы работы;
  - persisted retry timestamp и adaptive backoff после 429/временных ошибок;
  - автоматическое восстановление `RUNNING` units после рестарта;
  - ожидание доступности HH до полуночи соответствующего дня;
  - немедленный `PARSER_CONTRACT_BROKEN` без публикации частичного snapshot;
  - приватный HTML quarantine с ограничением размера и retention 24 часа;
  - единая транзакция `validate staging -> publish -> SUCCEEDED`;
  - постоянно работающий daily scheduler внутри API-процесса.
- API ручного запуска/возобновления и чтения текущего прогресса:
  `POST/GET /api/v1/jobs/{job_id}/runs/today`.
- Docker Compose для локального запуска и persistent volume.
- Полный React/TypeScript frontend: обзор, лента качества данных, сравнение профессий,
  дневной срез, задачи, persisted progress, события, настройки и CSV-выгрузка.
- 43 автоматических теста на доменные инварианты, parser contract, полный role catalog,
  60-дневную методологию,
  rate/backoff, конкурентный claim, restart recovery, midnight expiry, persistence, staging,
  атомарную публикацию, scheduler и API.

## Архитектура

```text
src/hhpulse/
├── domain/          # сущности, value objects, инварианты, state transitions
├── application/     # use cases и порты
├── infrastructure/  # HH HTML adapter, transport, SQLite adapters
└── api/             # HTTP boundary для web UI
frontend/
├── src/domain/      # frontend types and metric semantics
├── src/data/        # demo/HTTP repository adapters and queries
├── src/components/  # reusable controls, charts and job forms
└── src/pages/       # complete application routes
```

Зависимости направлены внутрь. `domain` не знает о FastAPI, SQLite, httpx и hh.ru HTML.
`application` зависит только от domain и Protocol-портов. Реализации находятся в `infrastructure`.

Подробно: [`docs/architecture.md`](docs/architecture.md).

## Локальный запуск

```bash
docker compose up --build
```

API будет доступен на `http://localhost:8080`, OpenAPI — на `http://localhost:8080/docs`.
Web UI будет доступен на `http://localhost:3000`. По умолчанию он собирается в полном
демонстрационном режиме. Для подключения существующих jobs/progress endpoints установите
`HHPULSE_FRONTEND_DATA_MODE=api` перед `docker compose up --build`; отсутствующие исторические
read models при этом честно показываются как недоступные.

Пример задачи "Москва, все роли":

```bash
curl -X POST http://localhost:8080/api/v1/jobs \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "Москва — все роли",
    "region_ids": ["1"],
    "role_selection_mode": "all",
    "role_ids": [],
    "max_concurrency": 1,
    "max_rps": 0.5,
    "user_agent_mode": "shared"
  }'
```

## Тесты

```bash
poetry install
poetry run pytest

cd frontend
npm ci
npm run lint
npm test
npm run build
```

## Что намеренно не сделано в этой итерации

Исполняемое ядро и frontend завершены. Пока нет Telegram/Prometheus/Grafana, WebSocket progress,
аналитических read models и dashboard API. Поэтому интерфейс имеет полноценный `demo`-адаптер,
а режим реального API уже подключает существующие jobs/progress endpoints и fail-closed показывает
отсутствующие аналитические маршруты. Требуемый backend-контракт описан в
[`frontend/docs/api-contract.md`](frontend/docs/api-contract.md).

Исполнение и аварийные гарантии описаны в [`docs/iteration-2.md`](docs/iteration-2.md).
