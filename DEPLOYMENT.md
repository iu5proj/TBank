# Руководство по деплою

## 1. Требования

Минимально:

- Docker Engine;
- Docker Compose v2;
- Python 3.11+ для локальных тестов;
- свободные порты `8000`, `8002`, `5433`, `6379`.

Для GPU-режима:

- NVIDIA GPU;
- свежий NVIDIA driver;
- NVIDIA Container Toolkit;
- успешная проверка:

```bash
docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi
```

## 2. Подготовка `.env`

```bash
cd /mnt/d/projects/MLtbank
cp .env.example .env
```

Для live-review с локальным Ollama в compose:

```env
ML_PREDICTOR_MODE=openai_compatible
ML_OPENAI_BASE_URL=http://ollama:11434/v1
ML_OPENAI_MODEL_NAME=gpt-oss:20b
ML_OPENAI_API_STYLE=ollama
ML_OPENAI_TIMEOUT=25
GPT_OSS_TIMEOUT=90
VACANCY_SOURCES=hh,trudvsem,habr,fixture
PARSER_ENABLE_FIXTURE_SOURCE=true
```

Для полностью детерминированной проверки без модели:

```env
ML_PREDICTOR_MODE=stub
```

## 3. Локальный запуск без GPU

```bash
cd /mnt/d/projects/MLtbank
docker compose --profile llm up -d ollama
docker compose exec ollama ollama pull gpt-oss:20b
docker compose up -d --build backend ml_service postgres redis
docker compose exec backend alembic upgrade head
```

Проверка:

```bash
curl -s http://127.0.0.1:8000/health; echo
curl -s http://127.0.0.1:8002/health; echo
```

## 4. Локальный запуск с GPU

```bash
cd /mnt/d/projects/MLtbank
docker compose -f docker-compose.yml -f docker-compose.gpu.yml --profile llm up -d ollama
docker compose exec ollama ollama pull gpt-oss:20b
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build backend ml_service postgres redis
docker compose exec backend alembic upgrade head
```

Проверить GPU внутри контейнера:

```bash
docker compose exec -T ollama nvidia-smi
```

Прогреть модель:

```bash
TIMEOUT_SECONDS=600 bash scripts/warm_ollama_gpu.sh
```

Проверить, что модель держится в памяти:

```bash
docker compose exec -T ollama ollama ps
```

На 8GB VRAM нормально увидеть частичный offload, например:

```text
PROCESSOR 57%/43% CPU/GPU
```

## 5. Миграции

Миграции выполняются из backend-контейнера:

```bash
docker compose exec backend alembic upgrade head
```

При production-like деплое миграции нужно выполнять до приема пользовательского
трафика.

## 6. Smoke test

Основной smoke:

```bash
bash scripts/live_review_smoke.sh
```

Ожидаемый результат:

```text
OK: ml_service is healthy
OK: backend is healthy
OK: analyze returned success
Summary: source=gpt-oss-20b vacancies=14/14 salary=200000/215000/250000 RUB confidence=medium:0.55
Top recommendation: Добавить подтверждение Kubernetes
```

Если smoke сообщает grounded fallback, это не авария. Это означает, что
локальная модель не успела или не вернула финальный JSON, а `ml_service`
вернул расчет по `market_evidence`.

## 7. Полный режим ожидания модели

Для live-review безопаснее короткий timeout. Если нужно именно дождаться
модель, пересоздайте контейнеры с увеличенными timeout:

```bash
GPT_OSS_TIMEOUT=180 ML_OPENAI_TIMEOUT=150 \
  docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --force-recreate backend ml_service

bash scripts/live_review_smoke.sh
```

Если результат уже закеширован как valid, поднимите `GPT_OSS_PROMPT_VERSION` в
`.env`, чтобы получить новый `request_hash`.

## 8. Production-like hardening

Перед реальным деплоем:

- задайте сильный `SECRET_KEY`;
- задайте `API_AUTH_TOKEN`;
- ограничьте `BACKEND_CORS_ORIGINS`;
- смените `POSTGRES_PASSWORD`;
- не публикуйте `.env`;
- отключите `DEBUG`;
- решите, нужен ли `fixture` в `VACANCY_SOURCES`;
- добавьте резервное копирование PostgreSQL volume;
- включите централизованные логи;
- ограничьте rate limit под ожидаемую нагрузку.

Пример production-like `.env`:

```env
DEBUG=false
API_AUTH_TOKEN=<strong-token>
SECRET_KEY=<strong-secret>
BACKEND_CORS_ORIGINS=["https://example.com"]
VACANCY_SOURCES=trudvsem,habr
PARSER_ENABLE_FIXTURE_SOURCE=false
```

## 9. Обновление версии

Стандартный порядок:

```bash
git pull
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build --force-recreate backend ml_service
docker compose exec backend alembic upgrade head
bash scripts/live_review_smoke.sh
```

Если менялся ML prompt:

1. обновите prompt file;
2. обновите `GPT_OSS_PROMPT_VERSION`;
3. пересоздайте backend;
4. прогоните smoke.

## 10. Остановка

Остановить контейнеры, сохранив volumes:

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml --profile llm down
```

Удалить volumes, включая БД и скачанную модель:

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml --profile llm down -v
```

Команду с `-v` используйте только если точно нужно очистить состояние.

