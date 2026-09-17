# hhPulse

Локальный сервис для ежедневного измерения конкуренции на рынке труда через агрегированные
счётчики поисковой выдачи hh.ru. 

## Локальный запуск

```bash
docker compose up --build
```

API будет доступен на `http://localhost:8080`, OpenAPI — на `http://localhost:8080/docs`.

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
python -m pip install -e '.[dev]'
pytest
```