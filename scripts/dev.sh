#!/usr/bin/env bash
# Linux/macOS counterpart of dev.ps1; run through `make`.
set -euo pipefail
cd "$(dirname "$0")/.."

RUN_DIR=.run

listening() { curl -s -o /dev/null "http://127.0.0.1:$1"; }

start_server() {
  local name=$1 dir=$2 port=$3
  shift 3
  if listening "$port"; then
    echo "$name already running"
    return
  fi
  (cd "$dir" && nohup "$@" > "../$RUN_DIR/$name.log" 2>&1 < /dev/null &)
}

wait_server() {
  local name=$1 url=$2
  for _ in $(seq 1 90); do
    curl -sf -o /dev/null "$url" && return
    sleep 1
  done
  tail -n 20 "$RUN_DIR/$name.log"
  echo "$name did not start, see $RUN_DIR/$name.log" >&2
  exit 1
}

stop_servers() {
  local pids
  for port in 8000 4200; do
    pids=$(lsof -ti "tcp:$port" -sTCP:LISTEN || true)
    if [ -n "$pids" ]; then kill $pids; fi
  done
}

start() {
  docker compose up -d --wait
  (cd backend && uv run alembic upgrade head)
  [ -d frontend/node_modules ] || (cd frontend && npm ci)
  mkdir -p "$RUN_DIR"
  start_server backend backend 8000 uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
  start_server frontend frontend 4200 npm start -- --host 127.0.0.1 --port 4200
  wait_server backend http://127.0.0.1:8000/readyz
  wait_server frontend http://127.0.0.1:4200
  echo "Backend:  http://localhost:8000/docs  (log: $RUN_DIR/backend.log)"
  echo "Frontend: http://localhost:4200       (log: $RUN_DIR/frontend.log)"
}

stop() {
  stop_servers
  docker compose down
}

clean() {
  stop_servers
  docker compose down --volumes --remove-orphans
  rm -rf "$RUN_DIR"
}

case "${1:-help}" in
  start) start ;;
  stop) stop ;;
  restart) stop && start ;;
  clean) clean ;;
  *)
    echo "make start    start the database, apply migrations, run backend and frontend in the background"
    echo "make stop     stop backend, frontend and the containers; data is kept"
    echo "make restart  stop, then start"
    echo "make clean    stop, then delete containers, volumes with the database data and logs; images are kept"
    ;;
esac
