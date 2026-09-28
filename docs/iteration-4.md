# Итерация 4 — однокнопочный локальный деплой

## Результат

Весь стек запускается одной командой:

```bash
./deploy.sh
```

Снаружи публикуется только `http://localhost:3000`. Nginx раздаёт SPA и
проксирует `/api`, `/docs`, `/openapi.json` и `/health` во внутренний API.
Отдельный порт backend на host больше не нужен.

## Изменения

- API переведён на multi-stage image: wheel и зависимости собираются отдельно,
  а runtime содержит только virtualenv и приложение.
- Frontend переведён на multi-stage image: Node.js и `node_modules` остаются в
  build stage, статический `dist` обслуживает непривилегированный Nginx.
- Для npm и pip включены BuildKit cache mounts.
- BuildKit-кэши получили стабильные идентификаторы, а сетевые `RUN`-шаги по
  умолчанию используют host network с IPv4-first для обхода проблем Docker DNS,
  VPN и split tunneling.
- Frontend image не устанавливает тестовые и lint-зависимости: в builder входят
  только приложение, TypeScript и Vite.
- Оба build context очищены `.dockerignore` от зависимостей, результатов сборки,
  тестов, локальных данных и служебных файлов.
- Compose ждёт healthcheck API перед запуском frontend.
- Контейнеры работают без root, capabilities и права записи в root filesystem.
- Добавлены persistent SQLite volume, `tmpfs`, PID limits, log rotation и
  `restart: unless-stopped`.
- `deploy.sh` создаёт `.env`, валидирует конфигурацию, собирает, запускает,
  дожидается готовности и при ошибке показывает диагностические логи.
- Данные не удаляются командами `stop` и `down`.

## Проверка

В среде подготовки выполнены:

```text
bash -n deploy.sh                         PASS
./deploy.sh --help                        PASS
python -m compileall -q src tests         PASS
python -m pip wheel --no-deps .           PASS
npm run lint                              PASS
npm run test                              PASS (7 tests)
npm run build                             PASS
npm ci --omit=dev && npm run build        PASS (121 packages instead of 323)
```

Полный `docker compose build/up` оставлен для ручного теста на целевой машине:
в среде подготовки Docker daemon отсутствует. Скрипт `./deploy.sh doctor`
проверяет daemon и итоговую Compose-конфигурацию до запуска.

## Ожидаемое время

Первый запуск по-прежнему должен скачать базовые образы. Показанные ранее
297 секунд на шаге `FROM node:24-alpine` — это сетевой pull, а не сборка кода.
После первого успешного скачивания повторный `./deploy.sh` использует локальные
слои и package caches; изменения исходников не требуют повторного pull.
