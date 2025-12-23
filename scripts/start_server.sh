#!/usr/bin/env bash
set -euo pipefail

cd /home/parser/code/ai_idea_gen

# 自动将.env文件中的变量读入环境变量
if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

exec uvicorn backend.main:app --reload --host 0.0.0.0 --port 8001 "$@"



