> Исторический контракт старого адаптера. Текущий сбор: [browser-contract.md](browser-contract.md).

# Контракт HeadHunter API для hhPulse

## Источники

Production использует только `https://api.hh.ru`:

- `GET /professional_roles` — полный каталог professional roles;
- `GET /vacancies` — `found`, clusters и список вакансий;
- `responses_count_enabled=true` — `counters.responses` в элементах выдачи.

Вакансии не парсятся с `hh.ru/search/vacancy`.

## Aggregate query

Базовые параметры:

```text
area=<id>
professional_role=<id>
no_magic=true
clusters=true
per_page=1
```

`per_page=1` выбран намеренно. Документация описывает `per_page=0` как режим только clusters без стандартных полей, тогда как hhPulse требует `found` как обязательный агрегат.

Дополнительная страта опыта добавляет документированный `experience=<id>`.

## Требуемые метрики

Сначала читаются clusters. Если cluster/option отсутствует, hhPulse делает точный fallback count с `per_page=1` для:

- `label=low_performance`;
- `label=with_salary`;
- `work_format=REMOTE`;
- `work_format=HYBRID`;
- `education=higher`;
- `experience=noExperience`.

Так отсутствие cluster option не превращается ошибочно в ноль.

## Точные отклики

Для основной страты (`experience=ANY`) hhPulse делает отдельный проход:

```text
responses_count_enabled=true
per_page=100
order_by=publication_time
```

В БД не сохраняются вакансии и их тексты. Из каждого item используются только `id` для дедупликации и `counters.responses`; результат сразу агрегируется в histogram.

API ограничивает глубину поисковой выдачи 2000. При больших выдачах клиент дробит диапазон по `date_from/date_to`. Итоговые элементы дедуплицируются по vacancy id.

Если из-за изменения выдачи во время run количество наблюдённых вакансий расходится с исходным `found`, histogram сохраняется, но mean/median не публикуются как завершённые метрики.

## Ошибки

- `401/403` — terminal authorization/access error;
- `429` — throttling, учитывается `Retry-After`, запрос переносится;
- `502/503/504` — временная недоступность, retry/backoff;
- `400` от сгенерированного запроса — contract error;
- неожиданный/некорректный JSON — contract error + JSON quarantine.

Никаких CAPTCHA solver, proxy rotation, random User-Agent и browser fingerprint tricks в production нет.
