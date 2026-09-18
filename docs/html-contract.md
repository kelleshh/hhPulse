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

Fail-closed правило: если HH перестал отдавать распознаваемый total или `searchClusters`, страница
не превращается в `0`; run должен быть остановлен как `PARSER_CONTRACT_BROKEN`.
