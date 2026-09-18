# Frontend API contract

Интерфейс использует уже существующие маршруты задач и текущего запуска без
изменений. Историческая аналитика и события пока работают только в
демонстрационном адаптере. Для режима `VITE_DATA_MODE=api` следующая backend
итерация должна реализовать эти read-only маршруты.

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/catalog/professional-roles` | Полный актуальный каталог ролей |
| `GET` | `/api/v1/analytics/overview?metric=hhIndex` | Лента дней, основной график, сводка публикаций |
| `GET` | `/api/v1/analytics/comparison` | Ряды по ролям, метрике, опыту и диапазону дат |
| `GET` | `/api/v1/analytics/snapshot` | Один опубликованный срез и все facet-распределения |
| `GET` | `/api/v1/alerts` | События источника, парсера и планировщика |
| `POST` | `/api/v1/alerts/{alert_id}/resolve` | Отметить событие разобранным |

Требования к ответам:

- даты — ISO `YYYY-MM-DD`, timestamps — ISO 8601 с timezone;
- разрыв исторического ряда — `null`, не `0`;
- значения долей — числа от `0` до `1`;
- серии имеют стабильный `id`, человекочитаемый `label` и массив `points`;
- frontend не вычисляет публикацию, полноту или терминальность run-а;
- аналитические endpoints читают только атомарно опубликованную history-таблицу.

Существующие `POST/GET /api/v1/jobs/{job_id}/runs/today` уже подключены. Поля
`effectiveRps`, `response429Count`, `currentRole`, `currentFilter` и `startedAt`
в подробном экране считаются опциональными до расширения progress DTO.
