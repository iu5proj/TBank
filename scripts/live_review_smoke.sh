#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_URL="${BACKEND_URL:-http://127.0.0.1:8000}"
ML_URL="${ML_URL:-http://127.0.0.1:8002}"
FIXTURE_PATH="${FIXTURE_PATH:-$ROOT_DIR/backend/tests/fixtures/analyze_python_backend_middle_force_refresh.json}"
WAIT_SECONDS="${WAIT_SECONDS:-90}"

wait_http() {
  local name="$1"
  local url="$2"
  local deadline=$((SECONDS + WAIT_SECONDS))

  until curl -fsS "$url" >/dev/null 2>&1; do
    if (( SECONDS >= deadline )); then
      echo "ERROR: $name did not become healthy at $url within ${WAIT_SECONDS}s" >&2
      return 1
    fi
    sleep 1
  done
  echo "OK: $name is healthy"
}

require_command() {
  local command_name="$1"
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "ERROR: required command is missing: $command_name" >&2
    return 1
  fi
}

require_command curl
require_command python3

wait_http "ml_service" "$ML_URL/health"
wait_http "backend" "$BACKEND_URL/health"

tmp_response="$(mktemp)"
trap 'rm -f "$tmp_response"' EXIT

http_code="$(
  curl -sS \
    -w "%{http_code}" \
    -o "$tmp_response" \
    -X POST "$BACKEND_URL/api/v1/analyze" \
    -H "Content-Type: application/json" \
    -d "@$FIXTURE_PATH"
)"

python3 - "$tmp_response" "$http_code" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
http_code = sys.argv[2]
payload = json.loads(path.read_text(encoding="utf-8"))

if http_code != "200":
    raise SystemExit(f"HTTP {http_code}: {payload}")
if payload.get("status") != "success":
    raise SystemExit(f"Analyze returned non-success response: {payload}")

data = payload["data"]
sample = data["market_sample"]
salary = data["salary_range"]

if sample["vacancies_used_for_estimation"] != sample["candidate_vacancies_received"]:
    raise SystemExit(f"Model did not use all current candidate vacancies: {sample}")
if salary["currency"] != "RUB":
    raise SystemExit(f"Unexpected salary currency: {salary}")
if not data["recommendations"]:
    raise SystemExit("Analyze response has no recommendations")

print("OK: analyze returned success")
print(
    "Summary: "
    f"source={payload.get('source')} "
    f"vacancies={sample['vacancies_used_for_estimation']}/{sample['candidate_vacancies_received']} "
    f"salary={salary['min']}/{salary['median']}/{salary['max']} {salary['currency']} "
    f"confidence={data['confidence']['level']}:{data['confidence']['score']}"
)
reason = data["confidence"].get("reason") or ""
if reason:
    print("Confidence reason:", reason)
    lowered = reason.lower()
    if payload.get("source") == "grounded-fallback" or "fallback" in lowered or "таймаут" in lowered or "timeout" in lowered:
        print(
            "NOTE: response used grounded fallback. Warmup removes model load time, "
            "but full analyze can still exceed ML_OPENAI_TIMEOUT on local gpt-oss. "
            "For a full model attempt, recreate ml_service/backend with higher "
            "ML_OPENAI_TIMEOUT and GPT_OSS_TIMEOUT."
        )
print("Top recommendation:", data["recommendations"][0]["title"])
PY
