#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

find_bootstrap_python() {
  if command -v python3 >/dev/null 2>&1; then
    command -v python3
    return 0
  fi
  if command -v python >/dev/null 2>&1; then
    command -v python
    return 0
  fi
  echo "ERROR: python3 or python is required to create local virtualenvs" >&2
  return 1
}

ensure_project_python() {
  local project_dir="$1"
  local venv_python="$project_dir/.venv/bin/python"
  if [[ ! -x "$venv_python" ]]; then
    local bootstrap_python
    bootstrap_python="$(find_bootstrap_python)"
    echo "Creating virtualenv: $project_dir/.venv" >&2
    "$bootstrap_python" -m venv "$project_dir/.venv"
  fi
  echo "$venv_python"
}

echo "== backend: install/check/test =="
(
  cd "$ROOT_DIR/backend"
  PYTHON_BIN="$(ensure_project_python "$PWD")"
  "$PYTHON_BIN" -m pip install -e ".[dev]"
  "$PYTHON_BIN" -m ruff check app tests
  "$PYTHON_BIN" -m pytest tests
)

echo "== ml_service: install/check/test =="
(
  cd "$ROOT_DIR/ml_service"
  PYTHON_BIN="$(ensure_project_python "$PWD")"
  "$PYTHON_BIN" -m pip install -e ".[dev]"
  "$PYTHON_BIN" -m ruff check app tests
  "$PYTHON_BIN" -m pytest tests
)
