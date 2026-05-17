# Live-review и диагностика

## Цель сценария

Показать backend-first ML/RAG пайплайн без ожидания долгой локальной генерации:

1. резюме кандидата;
2. рыночный сегмент;
3. сбор вакансий;
4. salary quantiles;
5. skill-gap;
6. рекомендации по росту зарплаты;
7. устойчивость при сбоях локальной модели.

## Быстрый сценарий показа

```bash
cd /mnt/d/projects/MLtbank

docker compose -f docker-compose.yml -f docker-compose.gpu.yml --profile llm up -d ollama
docker compose exec ollama ollama pull gpt-oss:20b

docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build --force-recreate backend ml_service
docker compose exec backend alembic upgrade head

TIMEOUT_SECONDS=600 bash scripts/warm_ollama_gpu.sh
bash scripts/live_review_smoke.sh
```

## Что говорить на демо

Короткий narrative:

- Backend не просто отправляет резюме в LLM.
- Сначала он строит сегмент рынка и подтягивает вакансии.
- Затем считает фактические рыночные квантильные значения.
- LLM не имеет права использовать внешние salary knowledge.
- Если LLM не вернула JSON, система не падает: используется grounded fallback
  по тем же вакансиям.
- Это важнее для production, чем ждать локальную модель на слабом железе.

## Проверка GPU

```bash
docker compose exec -T ollama nvidia-smi
docker compose exec -T ollama ollama ps
```

Ожидаемо:

```text
NAME           ID              SIZE     PROCESSOR          CONTEXT    UNTIL
gpt-oss:20b    ...             14 GB    57%/43% CPU/GPU    1024       29 minutes from now
```

`PROCESSOR 57%/43% CPU/GPU` нормально для RTX 3060 Ti 8GB.

## Почему модель может не вернуть JSON

Для `gpt-oss:20b` в Ollama возможны ситуации:

- модель возвращает `thinking`, но пустой final content;
- модель не успевает до `ML_OPENAI_TIMEOUT`;
- JSON-mode не гарантирует, что reasoning-модель успеет перейти в final output;
- часть модели находится на CPU, поэтому скорость ниже, чем на полной GPU
  загрузке.

Проект защищается так:

- prompt просит компактный JSON;
- Ollama вызывается через `/api/generate`;
- включены `format=json`, `think=false`, `raw=true`;
- `ml_service` пытается восстановить JSON из `response`, `message.content` и
  parseable `thinking`;
- если JSON все равно отсутствует, возвращается grounded fallback.

## Типовые симптомы

### `curl: (56) Recv failure: Connection reset by peer`

Часто возникает сразу после recreate контейнеров, пока uvicorn еще стартует.
Если затем `/health` проходит, это не ошибка.

### `ollama ps` пустой

Модель не загружена или была выгружена. Запустите:

```bash
TIMEOUT_SECONDS=600 bash scripts/warm_ollama_gpu.sh
```

### `context canceled` в логах Ollama

Клиент оборвал запрос по timeout. Для быстрого демо это допустимо, если backend
возвращает success через fallback.

Если нужно дождаться модели:

```bash
GPT_OSS_TIMEOUT=180 ML_OPENAI_TIMEOUT=150 \
  docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --force-recreate backend ml_service
```

### HH возвращает 403

HH защищен ddos-guard и может блокировать контейнерные запросы. Отключите HH:

```env
VACANCY_SOURCES=trudvsem,habr,fixture
```

Pipeline fail-open: остальные источники продолжат работать.

## Команды логов

```bash
docker compose logs --tail=120 backend
docker compose logs --tail=120 ml_service
docker compose logs --tail=120 ollama
docker compose logs -f --tail=120 ollama
```

`logs -f` должен висеть до `Ctrl+C`; это нормальный follow-режим.

## Локальные тесты

```bash
bash scripts/run_backend_ml_checks.sh
```

Скрипт создает/использует локальные `.venv` внутри `backend` и `ml_service`,
ставит dev-зависимости, запускает ruff и pytest.

