# Zarabotok ML/RAG

Backend-first реализация пайплайна оценки дохода по резюме из ТЗ
`TZ_dlya_Codex_Zarabotok_ML_RAG_GPT_OSS`.

## Документация

- [Архитектура](docs/ARCHITECTURE.md) - сервисы, request flow, данные, cache/lock, ML fallback.
- [Деплой](DEPLOYMENT.md) - локальный, GPU, production-like запуск, миграции, smoke checks.
- [API-контракт](docs/API_CONTRACT.md) - `/api/v1/analyze`, `/api/v1/parser/refresh`, структура ответа.
- [Live-review и диагностика](docs/LIVE_REVIEW.md) - сценарий показа, GPU warmup, типовые сбои.

Главный инвариант:

```text
one request_hash = one valid cached llm_salary_results row
```

Валидный результат по `request_hash` не пересчитывается. Failed-cache можно
заменить новым ответом, чтобы не отравлять локальное demo после разового сбоя
Ollama или невалидного JSON.

Backend валидирует вход, обновляет один рыночный сегмент, достает максимум
актуальных `candidate_vacancies` из целевого и близких смежных сегментов,
защищает LLM-вызов lock/cache, валидирует JSON ответа модели и сохраняет
valid/failed результат. Для стабильного live-review backend также готовит
детерминированный `market_evidence`: квантильную рыночную выборку, совпавшие
и недостающие навыки, приблизительный uplift навыков внутри переданных
вакансий и кандидаты рекомендаций. ML service использует эти факты как
grounding и, если локальная модель ушла в долгую генерацию или вернула только
thinking, возвращает быстрый grounded fallback без внешних рыночных знаний.

## Структура

- `backend/` - FastAPI, SQLAlchemy, Alembic, preflight, RAG retrieval, validation/storage.
- `ml_service/` - HTTP-граница модели: быстрый stub для тестов или прокси к локальному Ollama/gpt-oss runner.
- `parser/` - отдельный parser dataset от второго разработчика, сохранен для batch-сборов.
- `nginx/` - reverse proxy для docker-compose.
- `back/Samosir_tbank/` - исходная вложенная копия, из которой backend был перенесен в корень.

## Запуск

```bash
cp .env.example .env
docker compose up --build
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.seed_test_data
```

API docs:

```text
http://localhost:8000/docs
```

Smoke request:

```bash
curl -X POST http://localhost:8000/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "profile": {
      "title": "Python Backend Developer",
      "experience_years": 3,
      "location": "Москва",
      "skills": ["Python", "FastAPI", "PostgreSQL"],
      "resume_text": "Разрабатывал backend-сервисы на FastAPI",
      "current_salary": 150000
    },
    "options": {"target_salary": 250000, "force_refresh": false}
  }'
```

## Если HH заблокирован

HH не является обязательным источником. Отключите его в `.env`:

```env
VACANCY_SOURCES=trudvsem,habr,fixture
```

Каждый источник обрабатывается fail-open: ошибка HH/Habr/Trudvsem логируется,
refresh сегмента продолжается по оставшимся источникам. `fixture` нужен для
локальной проверки без внешней сети.

## Реальный gpt-oss endpoint

По умолчанию backend вызывает локальный `ml_service`:

```env
GPT_OSS_CLIENT_MODE=service
GPT_OSS_SERVICE_URL=http://ml_service:8001
GPT_OSS_ANALYZE_PATH=/analyze
```

Для OpenAI-compatible endpoint:

```env
GPT_OSS_CLIENT_MODE=openai_compatible
GPT_OSS_BASE_URL=http://llm-service:8000/v1
GPT_OSS_API_KEY=local-dev-key
GPT_OSS_MODEL_NAME=gpt-oss-20b
GPT_OSS_MODEL_VERSION=gpt-oss-20b-salary-v1
GPT_OSS_PROMPT_VERSION=salary_estimation_prompt_v13
```

Prompt лежит в `backend/app/prompts/salary_estimation_prompt_v13.txt`; изменение
`GPT_OSS_PROMPT_VERSION` меняет `request_hash`.

## Проверки

```bash
cd /mnt/d/projects/MLtbank
bash scripts/run_backend_ml_checks.sh
```

Ручной вариант:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m ruff check app tests
python -m pytest
alembic upgrade head
deactivate

cd ../ml_service
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m pytest tests/test_predictor.py
deactivate
```

## Live-review smoke

Для демонстрации без ручного разбора длинного `curl`:

```bash
cd /mnt/d/projects/MLtbank
docker compose -f docker-compose.yml -f docker-compose.gpu.yml --profile llm up -d --force-recreate ollama
docker compose exec ollama ollama pull gpt-oss:20b
docker compose up -d --build --force-recreate ml_service backend
docker compose exec backend alembic upgrade head
bash scripts/warm_ollama_gpu.sh
bash scripts/live_review_smoke.sh
```

Скрипт ждет `/health` у backend и `ml_service`, вызывает
`POST /api/v1/analyze` на fixture для middle Python backend developer и
проверяет, что ответ успешный, использует все переданные вакансии, возвращает
RUB-вилку и рекомендации. Если локальная модель думает слишком долго,
`ml_service` должен вернуть grounded fallback после `ML_OPENAI_TIMEOUT`, а не
уронить backend.

`scripts/warm_ollama_gpu.sh` нужен именно для GPU-прогрева перед показом. Он
проверяет `nvidia-smi` внутри compose-контейнера `ollama`, делает короткий
JSON-запрос к `/api/generate` с `format=json` и `think=false`, после чего оставляет
модель в памяти через `OLLAMA_KEEP_ALIVE`. Если в логах Ollama видно
`context canceled` примерно через `ML_OPENAI_TIMEOUT`, это означает, что
HTTP-клиент `ml_service` сам оборвал долгую загрузку модели. Для live-review это
не фатально: backend должен получить быстрый grounded fallback. Для демонстрации
реального GPU-path сначала выполните warmup-скрипт.

На RTX 3060 Ti `gpt-oss:20b` обычно загружается частично на GPU и частично на
CPU. `ollama ps` может показывать примерно `57%/43% CPU/GPU`; это нормально для
8GB VRAM. Быстрый live-review режим держит `ML_OPENAI_TIMEOUT=25`, поэтому
полный analyze может успеть не всегда и тогда вернется grounded fallback по
переданным вакансиям. Если нужно именно дождаться полного ответа модели, можно
пересоздать backend и ml_service с большим таймаутом:

```bash
GPT_OSS_TIMEOUT=180 ML_OPENAI_TIMEOUT=150 \
  docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --force-recreate backend ml_service
bash scripts/live_review_smoke.sh
```

Для live-review безопаснее оставить короткий таймаут: зритель не ждет модель,
а пайплайн все равно демонстрирует RAG-выборку, расчет рыночной вилки, skill-gap
и рекомендации.

## ML service: real gpt-oss runner

`ml_service` now has two runtime modes:

```env
ML_PREDICTOR_MODE=stub
```

keeps deterministic local smoke tests, while

```env
ML_PREDICTOR_MODE=openai_compatible
ML_OPENAI_BASE_URL=http://ollama:11434/v1
ML_OPENAI_API_KEY=local-dev-key
ML_OPENAI_MODEL_NAME=gpt-oss:20b
ML_OPENAI_API_STYLE=ollama
```

keeps backend pointed at `ml_service`, but makes `ml_service` call a real
model runner. With `ML_OPENAI_API_STYLE=ollama` it uses Ollama native
`/api/generate`; otherwise it uses OpenAI-compatible `/chat/completions`.

For local Ollama through docker compose:

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml --profile llm up -d --force-recreate ollama
docker compose exec ollama ollama pull gpt-oss:20b
bash scripts/warm_ollama_gpu.sh
```

Then set `ML_PREDICTOR_MODE=openai_compatible` in `.env` and recreate
`ml_service backend`.

If Docker cannot use the GPU, run Ollama on the Windows/WSL host instead and
point the containers to it:

```env
ML_OPENAI_BASE_URL=http://host.docker.internal:11434/v1
```

If NVIDIA Container Toolkit is not installed for Docker, use plain compose
instead:

```bash
docker compose --profile llm up -d ollama
```

## Manual vacancy parser activation

The regular `/api/v1/analyze` flow is unchanged. It can still refresh a segment
with `options.force_refresh=true`, but that also continues into salary analysis.

For parser-only warmup or diagnostics use:

```bash
curl -X POST http://localhost:8000/api/v1/parser/refresh \
  -H "Content-Type: application/json" \
  -d '{
    "profile": {
      "title": "Python Backend Developer",
      "experience_years": 3,
      "location": "Москва",
      "skills": ["Python", "FastAPI", "PostgreSQL"]
    },
    "sources": ["trudvsem", "fixture"],
    "dry_run": false
  }'
```

For source diagnostics without writing vacancies:

```bash
curl -X POST http://localhost:8000/api/v1/parser/refresh \
  -H "Content-Type: application/json" \
  -d '{
    "segment_key": "backend_developer:python:moscow:middle",
    "sources": ["hh", "trudvsem", "habr", "fixture"],
    "dry_run": true
  }'
```

The response includes per-source `status`, `fetched_count`, `usable_count`, and
`error`. Habr Career requires `HABR_CAREER_API_TOKEN`. HH can return 403 from
ddos-guard depending on IP/network; the parser treats source errors as
fail-open and continues with the remaining sources.
