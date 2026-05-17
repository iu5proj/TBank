#!/usr/bin/env bash
set -euo pipefail

MODEL="${MODEL:-gpt-oss:20b}"
OLLAMA_URL="${OLLAMA_URL:-}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-240}"
PROMPT="${PROMPT:-Return JSON with one boolean key named ok set to true.}"

require_command() {
  local command_name="$1"
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "ERROR: required command is missing: $command_name" >&2
    return 1
  fi
}

warmup_python() {
  cat <<'PY'
import json
import os
import time
import urllib.error
import urllib.request

model = os.environ["MODEL"]
prompt = os.environ["PROMPT"]
url = os.environ["OLLAMA_WARMUP_URL"]
timeout = float(os.environ.get("TIMEOUT_SECONDS", "240"))

payload = {
    "model": model,
    "stream": False,
    "format": "json",
    "raw": True,
    "think": False,
    "keep_alive": "30m",
    "prompt": prompt,
    "options": {
        "num_ctx": 1024,
        "num_predict": 128,
        "temperature": 0,
    },
}

request = urllib.request.Request(
    url,
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST",
)

started = time.monotonic()
try:
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8", errors="replace")
        status = response.status
except urllib.error.HTTPError as exc:
    body = exc.read().decode("utf-8", errors="replace")
    raise SystemExit(f"Ollama warmup failed with HTTP {exc.code}: {body[:1000]}")
except Exception as exc:
    raise SystemExit(f"Ollama warmup failed: {exc}") from exc

if status != 200:
    raise SystemExit(f"Ollama warmup failed with HTTP {status}: {body[:1000]}")

payload = json.loads(body)
message = payload.get("message") if isinstance(payload, dict) else None
content = payload.get("response") if isinstance(payload, dict) else ""
if not isinstance(content, str) or not content.strip():
    content = message.get("content") if isinstance(message, dict) else ""
if not isinstance(content, str) or not content.strip():
    content = payload.get("thinking") if isinstance(payload, dict) else ""
if not isinstance(content, str) or not content.strip():
    content = message.get("thinking") if isinstance(message, dict) else ""

print("OK: Ollama warmup completed")
print("Response:", content.strip() or "<empty>")
if not content.strip():
    print("WARN: model loaded, but warmup response had no final JSON content")
print("Elapsed seconds:", round(time.monotonic() - started, 2))
print("Total duration ns:", payload.get("total_duration"))
print("Load duration ns:", payload.get("load_duration"))
PY
}

warm_via_compose() {
  require_command docker

  echo "Checking GPU visibility inside compose ollama service..."
  local smi_out
  local smi_err
  smi_out="$(mktemp)"
  smi_err="$(mktemp)"
  if docker compose exec -T ollama nvidia-smi >"$smi_out" 2>"$smi_err"; then
    sed -n '1,16p' "$smi_out"
  else
    echo "WARN: nvidia-smi is not available inside ollama container; continuing with model warmup." >&2
    sed -n '1,12p' "$smi_err" >&2 || true
  fi
  rm -f "$smi_out" "$smi_err"

  echo "Warming Ollama compose model=$MODEL; timeout=${TIMEOUT_SECONDS}s"
  if docker compose exec -T ml_service python -c "print('ok')" >/dev/null 2>&1; then
    echo "Posting warmup through running ml_service container..."
    warmup_python | docker compose exec -T \
      -e MODEL="$MODEL" \
      -e PROMPT="$PROMPT" \
      -e TIMEOUT_SECONDS="$TIMEOUT_SECONDS" \
      -e OLLAMA_WARMUP_URL="http://ollama:11434/api/generate" \
      ml_service python -
  else
    local container_id
    container_id="$(docker compose ps -q ollama)"
    if [[ -z "$container_id" ]]; then
      echo "ERROR: compose service 'ollama' is not running" >&2
      return 1
    fi
    echo "Posting warmup through one-shot python container in ollama network namespace..."
    warmup_python | docker run --rm \
      --network "container:$container_id" \
      -e MODEL="$MODEL" \
      -e PROMPT="$PROMPT" \
      -e TIMEOUT_SECONDS="$TIMEOUT_SECONDS" \
      -e OLLAMA_WARMUP_URL="http://127.0.0.1:11434/api/generate" \
      python:3.11-slim python -
  fi
  echo "Loaded models:"
  docker compose exec -T ollama ollama ps || true
}

warm_via_http() {
  require_command curl
  require_command python3

  tmp_response="$(mktemp)"
  trap 'rm -f "$tmp_response"' EXIT

  echo "Warming Ollama model=$MODEL via $OLLAMA_URL; timeout=${TIMEOUT_SECONDS}s"

  http_code="$(
    curl -sS \
      --max-time "$TIMEOUT_SECONDS" \
      -w "%{http_code}" \
      -o "$tmp_response" \
      -X POST "$OLLAMA_URL/api/generate" \
      -H "Content-Type: application/json" \
      -d @- <<JSON
{
  "model": "$MODEL",
  "stream": false,
  "format": "json",
  "raw": true,
  "think": false,
  "keep_alive": "30m",
  "prompt": "$PROMPT",
  "options": {
    "num_ctx": 1024,
    "num_predict": 128,
    "temperature": 0
  }
}
JSON
  )"

  python3 - "$tmp_response" "$http_code" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
http_code = sys.argv[2]
text = path.read_text(encoding="utf-8", errors="replace")

if http_code != "200":
    raise SystemExit(f"Ollama warmup failed with HTTP {http_code}: {text[:1000]}")

payload = json.loads(text)
message = payload.get("message") if isinstance(payload, dict) else None
content = payload.get("response") if isinstance(payload, dict) else ""
if not isinstance(content, str) or not content.strip():
    content = message.get("content") if isinstance(message, dict) else ""
if not isinstance(content, str) or not content.strip():
    content = payload.get("thinking") if isinstance(payload, dict) else ""
if not isinstance(content, str) or not content.strip():
    content = message.get("thinking") if isinstance(message, dict) else ""

print("OK: Ollama warmup completed")
print("Response:", content.strip() or "<empty>")
print("Total duration ns:", payload.get("total_duration"))
print("Load duration ns:", payload.get("load_duration"))
PY
}

if [[ -n "$OLLAMA_URL" ]]; then
  warm_via_http
else
  warm_via_compose
fi
