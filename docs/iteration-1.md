# План работ

## Итерация 1 — фундамент (выполнено)

- [x] выделить domain entities/value objects и инварианты;
- [x] определить application ports;
- [x] реализовать use case создания/list/get/enable analysis jobs;
- [x] реализовать динамическое построение crawl plan по полному официальному role catalog;
- [x] реализовать HH query builder для vacancy/resume и 60-дневного окна резюме;
- [x] реализовать generic parser `searchClusters`;
- [x] реализовать async transport, RPS/concurrency и adaptive backoff;
- [x] реализовать SQLite persistence для jobs/runs/units;
- [x] реализовать staging -> atomic publish persistence;
- [x] поднять FastAPI boundary;
- [x] покрыть критические инварианты тестами;
- [x] добавить Docker Compose.

## Итерация 2 — исполняемый дневной crawl

- [ ] `PrepareOrResumeDailyRun` с детерминированными crawl-unit IDs;
- [ ] worker pool с пользовательским concurrency;
- [ ] recovery после рестарта контейнера;
- [ ] ожидание доступности hh.ru до конца московского дня;
- [ ] отдельная классификация transport throttling vs parser contract failure;
- [ ] canary/preflight HTML contract check перед большим run;
- [ ] ограниченный quarantine HTML только для parser failure;
- [ ] success/failure lifecycle и atomic publish;
- [ ] REST endpoints start/resume/cancel/status;
- [ ] WebSocket/SSE live progress.

## Итерация 3 — наблюдаемость

- [ ] Prometheus metrics;
- [ ] Grafana dashboard crawler health;
- [ ] Telegram notifications;
- [ ] retention для технических метрик/quarantine.

## Итерация 4 — аналитические read models

- [ ] history queries;
- [ ] daily HH-index;
- [ ] `<10 откликов` absolute/share;
- [ ] salary visibility share;
- [ ] experience strata;
- [ ] work-format/employment/schedule distributions;
- [ ] 1/7/30-day deltas;
- [ ] normalized-to-100 comparison series;
- [ ] compare multiple roles and compare strata of one role.

## Итерация 5 — web UI

- [ ] task constructor;
- [ ] persisted settings;
- [ ] real-time progress;
- [ ] dashboard shell;
- [ ] charts and role comparison.
