#!/usr/bin/env bash
set -euo pipefail

cd /home/parser/code/ai_idea_gen

# 默认端口（可通过环境变量 PORT 或参数 --port 覆盖）
PORT="${PORT:-8001}"

# 从参数中解析 --port / --port=xxxx（并移除，避免传给 uvicorn 重复）
UVICORN_EXTRA_ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --port)
      shift
      PORT="${1:-$PORT}"
      shift
      ;;
    --port=*)
      PORT="${1#--port=}"
      shift
      ;;
    *)
      UVICORN_EXTRA_ARGS+=("$1")
      shift
      ;;
  esac
done

# 自动将.env文件中的变量读入环境变量
if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

echo "==> 准备启动后端：host=0.0.0.0 port=${PORT}"

# 获取监听该端口的进程 PID（尽量使用 ss 的过滤语法，避免 grep 误匹配）
get_listen_pids() {
  local port="$1"
  # ss 过滤：sport = :PORT
  ss -ltnp "sport = :${port}" 2>/dev/null \
    | sed -n 's/.*pid=\([0-9]\+\).*/\1/p' \
    | sort -u
}

# 如果端口已被占用，尝试自动结束占用进程
PIDS="$(get_listen_pids "${PORT}" || true)"
if [[ -n "${PIDS}" ]]; then
  echo "==> 检测到端口 ${PORT} 已被占用，尝试停止进程：${PIDS}"
  # 先优雅退出
  for pid in ${PIDS}; do
    kill -TERM "${pid}" 2>/dev/null || true
  done

  # 等待最多 5 秒
  for _ in {1..10}; do
    sleep 0.5
    STILL="$(get_listen_pids "${PORT}" || true)"
    [[ -z "${STILL}" ]] && break
  done

  # 仍存在则强杀
  STILL="$(get_listen_pids "${PORT}" || true)"
  if [[ -n "${STILL}" ]]; then
    echo "==> 仍有进程占用端口 ${PORT}，强制结束：${STILL}"
    for pid in ${STILL}; do
      kill -KILL "${pid}" 2>/dev/null || true
    done
  fi
fi

# 设置日志级别为 INFO，确保能看到 FeishuClient 的调试日志
exec uvicorn backend.main:app --reload --host 0.0.0.0 --port "${PORT}" --log-level info "${UVICORN_EXTRA_ARGS[@]}"



