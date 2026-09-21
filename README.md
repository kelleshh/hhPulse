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
- Один синхронный `requests.Session` на дневной запуск; блокирующий вызов вынесен из event loop
  FastAPI через `asyncio.to_thread`.
- После каждого ответа выдерживается пауза из усечённого нормального распределения
  `N(1,35; 0,15²)` в строгих границах 0,9–1,8 секунды.
- Адаптивный backoff: 429/502/503/504 только замедляют клиент; лимит пользователя никогда не
  превышается.
- Один постоянный User-Agent и один последовательный HTTP-обработчик. Старые задачи с
  per-worker режимом автоматически переводятся в безопасный профиль при старте.
- Профессии случайно переставляются один раз на запуск с полным покрытием ID. Сначала строго
  выполняется фаза всех резюме, затем в том же порядке фаза всех вакансий.
- Persisted control-plane на SQLite/WAL: задачи, дневные run-ы, crawl-unit-ы.
- Staging/publish модель: частичный run можно сохранять и продолжать после рестарта, а в
  published history он попадает только целиком.
- FastAPI endpoints для создания, чтения, списка, включения/выключения и каскадного удаления задач.
- Исполняемое ядро второй итерации:
  - `PrepareOrResumeDailyRun` с одной последовательной preflight-проверкой;
  - атомарное создание persisted crawl units;
  - async worker pool с атомарным claim каждой единицы работы;
  - persisted retry timestamp и adaptive backoff после 429/временных ошибок;
  - автоматическое восстановление `RUNNING` units после рестарта;
  - ожидание доступности HH до полуночи соответствующего дня;
  - немедленный `PARSER_CONTRACT_BROKEN` без публикации частичного snapshot;
  - ручное продолжение после исправления парсера с сохранением уже собранного checkpoint;
  - приватный HTML quarantine с ограничением размера и retention 24 часа;
  - единая транзакция `validate staging -> publish -> SUCCEEDED`;
  - постоянно работающий daily scheduler внутри API-процесса.
- API ручного запуска/возобновления и чтения текущего прогресса:
  `POST/GET /api/v1/jobs/{job_id}/runs/today`.
- Однокнопочный Docker Compose deploy, многостадийные образы, healthchecks и persistent volume.
- Реальные аналитические read models поверх атомарно опубликованных наблюдений: временные ряды,
  срезы фасетов, матрица всех профессий, описательная статистика и системные события.
- Полный React/TypeScript frontend: обзор, шесть геометрий графиков, сравнение профессий,
  расширенный дневной срез, плотный пульт всех профессий, живой журнал сбора, задачи,
  события, настройки и CSV-выгрузка.
- 55 автоматических тестов на доменные инварианты, parser contract, нулевую выдачу,
  восстановление после исправления парсера, полный role catalog,
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

Зависимости направлены внутрь. `domain` не знает о FastAPI, SQLite, requests и hh.ru HTML.
`application` зависит только от domain и Protocol-портов. Реализации находятся в `infrastructure`.

Подробно: [`docs/architecture.md`](docs/architecture.md).

## Локальный запуск

```bash
./deploy.sh
```

Скрипт проверит Docker, при первом запуске создаст `.env`, соберёт образы, поднимет сервисы,
дождётся healthcheck и откроет браузер. Единственная внешняя точка входа —
`http://localhost:3000`. API доступен через неё же: `/api`, `/docs`, `/openapi.json`, `/health`.

Docker-сборка всегда запускает frontend в реальном API-режиме. Свежая база закономерно пуста:
создайте задачу, запустите сбор и следите за транзакционным журналом прямо в её карточке. После
атомарной публикации дневного среза заполнятся обзор, сравнения и пульт профессий.

Остальные команды и устройство сборки: [`docs/deployment.md`](docs/deployment.md).

Пример задачи "Москва, все роли":

```bash
curl -X POST http://localhost:3000/api/v1/jobs \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "Москва — все роли",
    "region_ids": ["1"],
    "role_selection_mode": "all",
    "role_ids": [],
    "max_concurrency": 1,
    "max_rps": 1.0,
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

## Границы текущей версии

Прогресс и живой журнал обновляются коротким опросом API раз в две секунды; WebSocket пока не
нужен. Telegram, Prometheus и Grafana не входят в локальный продукт. Demo-адаптер сохранён только
для изолированных frontend-тестов и разработки; production Compose всегда использует реальные
SQLite, HH API и аналитические маршруты.

Исполнение и аварийные гарантии описаны в [`docs/iteration-2.md`](docs/iteration-2.md).
