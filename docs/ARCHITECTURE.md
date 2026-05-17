# Архитектура Zarabotok ML/RAG

## Назначение

Проект оценивает рыночную зарплатную вилку по резюме кандидата. Основной
сценарий: пользователь передает резюме на одну позицию, например `Middle Python
Backend Developer`, а система:

1. нормализует профиль;
2. определяет рыночный сегмент и близкие смежные сегменты;
3. собирает вакансии из подключенных источников;
4. строит `market_evidence` по фактическим вакансиям;
5. вызывает локальную модель gpt-oss через `ml_service`;
6. валидирует и нормализует JSON;
7. сохраняет результат в PostgreSQL и возвращает стабильный API-ответ.

Важная инженерная идея: backend не перекладывает весь расчет на LLM. Backend
сам готовит рыночные факты, квантильную вилку, skill-gap и кандидаты
рекомендаций. Модель используется как reasoning/wording слой. Если локальная
модель не успела, вернула только thinking или сломала JSON, `ml_service`
возвращает grounded fallback по тем же рыночным данным.

## Сервисы

### `backend`

FastAPI-сервис на порту `8000`.

Отвечает за:

- публичный API `/api/v1/analyze`;
- preflight профиля и сегмента;
- загрузку/обновление вакансий;
- подготовку `market_evidence`;
- lock/cache для LLM-вызовов;
- валидацию ответа модели;
- сохранение `valid` и `failed` результатов в PostgreSQL.

### `ml_service`

FastAPI-сервис на внутреннем порту `8001`, наружу обычно проброшен как `8002`.

Режимы:

- `ML_PREDICTOR_MODE=stub` - детерминированный локальный stub для быстрых тестов;
- `ML_PREDICTOR_MODE=openai_compatible` - прокси к локальному runner модели.

Для Ollama используется `ML_OPENAI_API_STYLE=ollama`. В этом режиме `ml_service`
вызывает Ollama native `/api/generate` с:

- `format=json`;
- `think=false`;
- компактным prompt;
- коротким output contract, который backend затем нормализует до строгого
  ответа.

### `ollama`

Локальный runner gpt-oss. Может запускаться:

- в Docker Compose;
- на Windows/WSL host с `ML_OPENAI_BASE_URL=http://host.docker.internal:11434/v1`.

GPU-override лежит в `docker-compose.gpu.yml`. На RTX 3060 Ti 8GB модель
обычно грузится частично в GPU и частично в CPU. Это нормально: `ollama ps`
может показывать `57%/43% CPU/GPU`.

### `postgres`

Хранит:

- рыночные сегменты;
- вакансии;
- результаты LLM;
- служебные данные миграций.

Наружу порт пробрасывается как `5433`, чтобы не конфликтовать с локальным
PostgreSQL.

### `redis`

Используется для lock вокруг LLM-вызова, чтобы одинаковый `request_hash` не
порождал несколько параллельных дорогих запросов.

### `nginx`

Опциональный reverse proxy. Для backend-first live-review можно не использовать.

## Основной request flow

1. Клиент вызывает `POST /api/v1/analyze`.
2. Backend валидирует payload.
3. Backend строит `segment_key`, например:
   `backend_developer:python:moscow:middle`.
4. Если `force_refresh=true` или сегмент устарел, backend обновляет вакансии.
5. Источники вакансий вызываются fail-open:
   - `hh`;
   - `trudvsem`;
   - `habr`;
   - `fixture`.
6. Backend сохраняет вакансии с upsert по `(source, source_vacancy_id)`.
7. Backend выбирает актуальные вакансии целевого и близких сегментов.
8. Backend строит `market_evidence`:
   - salary quantiles;
   - matched skills;
   - missing skills;
   - sample uplift по навыкам;
   - recommendation candidates.
9. Backend считает `request_hash`.
10. Если есть `valid` cache, он возвращается без пересчета.
11. Если есть только `failed` cache, он может быть заменен новым результатом.
12. Backend берет Redis lock.
13. Backend вызывает `ml_service`.
14. `ml_service` вызывает Ollama или возвращает grounded fallback.
15. Backend валидирует строгий JSON-контракт.
16. Backend сохраняет `llm_salary_results`.
17. Клиент получает единый response envelope.

## Cache invariant

Главный инвариант:

```text
one request_hash = one valid cached llm_salary_results row
```

Валидный результат immutable. Это защищает live-review и production-like
сценарии от непредсказуемого дрейфа модели.

Failed-result не считается финальным. Его можно заменить новым результатом,
чтобы разовый сбой Ollama не отравлял локальную демонстрацию.

`request_hash` зависит от:

- профиля;
- сегмента;
- версии данных сегмента;
- версии модели;
- `GPT_OSS_PROMPT_VERSION`;
- подготовленного input payload.

Если нужно принудительно обойти старый valid cache после изменения prompt или
ML-логики, поднимите `GPT_OSS_PROMPT_VERSION`.

## Данные

### `market_segments`

Один ряд на рыночный сегмент:

- `segment_key`;
- роль;
- специализация;
- регион;
- опыт;
- версия данных;
- дата успешного refresh;
- количество вакансий.

### `vacancies`

Нормализованные вакансии:

- источник;
- id вакансии в источнике;
- salary min/max net;
- валюта;
- location;
- skills;
- raw payload.

### `llm_salary_results`

Результаты анализа:

- `request_hash`;
- snapshot профиля;
- segment;
- model/prompt metadata;
- input payload;
- output payload;
- validation status;
- validation errors.

## ML contract

Модель может вернуть неполный JSON, generic factors или не все id вакансий.
`ml_service` чинит типичные дрейфы:

- приводит salary к полным RUB integer;
- расширяет `used_vacancy_ids` до всех релевантных candidate vacancies;
- заменяет generic рекомендации на grounded `market_evidence`;
- нормализует factor impact и confidence level;
- возвращает fallback, если JSON отсутствует.

Строгая финальная проверка остается на backend.

## Почему fallback допустим

Fallback не использует внешние рыночные знания. Он строится только из:

- `candidate_vacancies`;
- `market_evidence`;
- профиля кандидата.

Поэтому он сохраняет главный смысл ТЗ: расчет зарплаты по рынку вакансий и
рекомендации по skill-gap. Модель в этом случае не придумывает зарплаты, а
только временно исключается из критического пути.

## Основные конфигурационные переменные

| Переменная | Назначение |
| --- | --- |
| `ML_PREDICTOR_MODE` | `stub` или `openai_compatible` |
| `ML_OPENAI_API_STYLE` | `ollama` или `openai` |
| `ML_OPENAI_BASE_URL` | URL runner модели |
| `ML_OPENAI_MODEL_NAME` | имя модели, например `gpt-oss:20b` |
| `ML_OPENAI_TIMEOUT` | timeout вызова модели из `ml_service` |
| `GPT_OSS_TIMEOUT` | timeout вызова `ml_service` из backend |
| `GPT_OSS_PROMPT_VERSION` | версия prompt/hash cache |
| `VACANCY_SOURCES` | список источников вакансий |
| `PARSER_ENABLE_FIXTURE_SOURCE` | включает deterministic fixture source |
| `OLLAMA_KEEP_ALIVE` | сколько держать модель в памяти |
| `OLLAMA_LOAD_TIMEOUT` | внутренний timeout загрузки модели в Ollama |

