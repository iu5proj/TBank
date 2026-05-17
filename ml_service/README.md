# GPT-OSS-Compatible Model Service

This service is the replaceable model boundary for the backend.

The important endpoint for the MVP is:

```text
POST /analyze
```

Backend sends one payload containing:

- `request_hash`
- `profile`
- `segment`
- `candidate_vacancies`
- `market_evidence`
- `rules`

The service must return the strict GPT-OSS salary result JSON:

- `market_sample`
- `salary_range`
- `confidence`
- `matched_skills`
- `missing_skills`
- `factor_analysis`
- `recommendations`

The service can run in deterministic `stub` mode or in `openai_compatible`
mode. In `openai_compatible` mode it can call Ollama native `/api/chat`
(`ML_OPENAI_API_STYLE=ollama`) or an OpenAI-compatible `/chat/completions`
runner. The response shape stays stable in every mode.

For live-review stability, the service normalizes model output against
`candidate_vacancies` and `market_evidence`. If a local Ollama call times out,
returns HTTP 5xx, or emits only thinking without final JSON, the service returns
a grounded deterministic fallback instead of making the backend fail.

`POST /predict` is still present only as a legacy compatibility endpoint for
old tests/scripts. New backend code uses `/analyze`.

Run locally:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```
