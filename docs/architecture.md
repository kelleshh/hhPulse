# Архитектура hhPulse personal fork

## 1. Главный инвариант продукта

MVP не моделирует отдельную вакансию или отдельное резюме. Атомарный факт — агрегированное
наблюдение поисковой выдачи hh.ru:

```text
observation_date × region × professional_role × experience × search_target
    -> total_count + facet_counts
```

`search_target` принимает `vacancy` или `resume`. HH-индекс вычисляется как:

```text
active_resumes_60d / active_vacancies
```

При `vacancies == 0` значение индекса отсутствует, а не становится бесконечностью.

## 2. Aggregate roots и сущности

### AnalysisJob

Пользовательская задача наблюдения. Содержит scope, расписание, методологию, max concurrency,
max RPS и UA policy. Режим `ALL` запрещает явный список role IDs; режим `SELECTED` требует его.

### CrawlRun

Один дневной прогон одной задачи. Переходы состояния контролируются доменной моделью:

```text
PLANNED -> RUNNING <-> WAITING_SOURCE
RUNNING -> SUCCEEDED
RUNNING/WAITING_SOURCE -> PARSER_BROKEN | FAILED | EXPIRED
```

`SUCCEEDED` запрещён, пока `completed_units != total_units`. В runtime этот переход выполняется
в одной SQLite-транзакции с проверкой всех unit-ов, проверкой staging, переносом наблюдений и
очисткой staging. Состояние `SUCCEEDED` без опубликованного snapshot невозможно.
`PARSER_BROKEN`, `FAILED`, `EXPIRED` и `SUCCEEDED` — терминальные состояния.

### CrawlUnit

Минимальная возобновляемая единица crawl — один `SearchQuery`. Она хранится отдельно, поэтому
рестарт процесса не уничтожает прогресс. 429 переводит orchestration в ожидание/retry, но не
обнуляет успешные unit-ы.

### SearchObservation

Неизменяемый результат одного запроса: `SearchQuery + ParsedSearchPage`.

## 3. Value objects

- `ProfessionalRole`, `Region`;
- `RateLimitPolicy`;
- `DailySchedule`;
- `Methodology`;
- `SearchQuery`, `QueryFilter`;
- `FacetGroup`, `FacetOptionCount`;
- `ParsedSearchPage`;
- `MarketSnapshot`, `HhIndex`.

Facet-модель намеренно generic. Новая группа счётчиков в `searchClusters` не требует нового класса
или `if` в parser-е.

## 4. Application layer

Application знает только порты:

- `AnalysisJobRepository`;
- `CrawlRunRepository`;
- `CrawlUnitRepository`;
- `ObservationRepository`;
- `MarketSource`;
- `Clock`.

`BuildDailyCrawlPlan` не содержит списка профессий. Для `role_selection_mode=all` он получает
актуальный полный catalog через `MarketSource.discover_roles()` и строит детерминированный plan.
HH HTML facet не используется как каталог: он зависит от текущей выдачи и не содержит роли с
нулём результатов. Инфраструктурный адаптер загружает официальный справочник
`/professional_roles`, разворачивает 27 категорий и дедуплицирует роли по ID.

## 5. Infrastructure layer

### HH adapter

`HhSearchPageParser` работает по semantic contract:

1. в документе должен находиться числовой result total;
2. должен декодироваться server-rendered `searchClusters`;
3. должен присутствовать хотя бы один facet с count.

Если contract не выполнен — `HhParserContractBroken`. Ноль не подставляется молча.

### Transport

`AdaptiveThrottle` разделяет два ограничения:

- maximum in-flight requests;
- maximum requests per second.

Backoff может только уменьшать фактическую скорость. 429 не используется как сигнал для обхода
ограничений или смены идентичности клиента.

### Persistence

SQLite/WAL выбран для первой персональной версии по KISS/YAGNI: объекты — агрегированные числа,
а не десятки миллионов вакансий. Persistence спрятан за портами и заменяется без изменения domain
или application.

Частичные данные лежат в `staged_search_observations`. `publish_completed()` проверяет целостность
run-а и одной транзакцией переносит полный набор в `search_observations`.

`SqliteCrawlExecutionRepository` является aggregate repository для всего исполняемого run. Он
атомарно выполняет claim, завершение unit-а вместе со staging и счётчиком run-а, parser abort,
expiration и publish. Отдельных несогласованных repository-вызовов для этих переходов нет.

## 6. API layer

FastAPI — внешний адаптер для localhost UI. DTO Pydantic не попадают в domain.

Текущие endpoints:

```text
GET   /health
POST  /api/v1/jobs
GET   /api/v1/jobs
GET   /api/v1/jobs/{id}
PATCH /api/v1/jobs/{id}/enabled
POST  /api/v1/jobs/{id}/runs/today
GET   /api/v1/jobs/{id}/runs/today
```

## 7. Что не смешивается

- HTML selectors/JSON keys не находятся в domain.
- SQL не находится в use cases.
- FastAPI models не являются domain entities.
- Retry/backoff не находится в parser-е.
- HH-index не рассчитывается в frontend.
