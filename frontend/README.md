# Zarabotok Frontend

Next.js frontend for the Zarabotok monorepo. The main user flow sends a resume profile to `POST /api/v1/analyze` and renders the GPT-OSS salary analysis contract returned by the backend.

## Backend Contract

The frontend expects the backend in `../backend`:

- `POST /api/v1/analyze` for salary analysis
- `POST /api/v1/resumes`, `GET /api/v1/resumes/{id}`, `PATCH /api/v1/resumes/{id}` for resume drafts
- `GET /health` for availability checks
- successful analyze responses may have `source=gpt-oss-20b`, `source=grounded-fallback`, or `source=cache`

The old `/api/v1/estimates`, `/api/v1/recommendations`, and `/api/v1/history` calls are not used.

## Local Run

```bash
npm install
npm run dev
```

By default, the frontend uses `NEXT_PUBLIC_API_URL=/api/v1`. In development, `next.config.ts` rewrites `/api/*` to `http://localhost:8000/api/*`, so the FastAPI backend should be running on port `8000`.

From the monorepo root, the production-like path is:

```bash
docker compose up -d --build frontend nginx backend ml_service postgres redis
```

Then open `http://localhost`.

For direct backend calls:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1 npm run dev
```

If backend `API_AUTH_TOKEN` is enabled for a private demo, set
`NEXT_PUBLIC_API_AUTH_TOKEN` to the same value before building. Do not treat a
`NEXT_PUBLIC_*` value as a secret in a public browser deployment.

## Checks

```bash
npm run lint
npm run build
```
