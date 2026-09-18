# HH HTML contract, исследованный для MVP

В сохранённой странице hh.ru серверный state содержит `searchClusters`. Один HTTP response уже
несёт множество агрегированных счётчиков, поэтому crawler не должен запрашивать каждую метрику
отдельно.

На исследованном vacancy HTML встречаются, среди прочего:

- `professional_role`;
- `experience`: `noExperience`, `between1And3`, `between3And6`, `moreThan6`;
- `education`: `not_required_or_not_specified`, `higher`, `special_secondary`;
- `work_format`: `ON_SITE`, `HYBRID`, `REMOTE`, `FIELD_WORK`;
- `employment_form`;
- `compensation_frequency`;
- `work_schedule_by_days`;
- `working_hours`;
- label facet с `with_salary`, `low_performance` и другими готовыми counts.

Resume HTML также содержит server-side clusters, включая professional role, experience,
work format, employment form, schedule и другие характеристики.

Parser не имеет whitelist этих групп: он сохраняет все группы, где HH отдал целочисленный
`count`. Product/analytics layer позже решит, какие facets показывать в конкретном dashboard.

Нулевая выдача является валидным наблюдением: HH показывает семантический заголовок
`По запросу ничего не найдено` вместо строки `Найдено 0 вакансий`. Парсер принимает ноль только
по видимому `h1/h2[data-qa=title]` и всё равно требует корректный `searchClusters`.

Fail-closed правило сохраняется: произвольная страница без числового total и без точного
заголовка нулевой выдачи не превращается в `0`; run останавливается как
`PARSER_CONTRACT_BROKEN`. После обновления кода пользователь может вручную продолжить такой run:
успешные units и staging сохраняются, отменённые units возвращаются в очередь.
