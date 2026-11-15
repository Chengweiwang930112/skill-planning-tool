# Local development on Windows. Run from cmd, PowerShell or Git Bash: `make start`.
SHELL := cmd.exe

# 127.0.0.1 rather than localhost, which Windows may resolve to ::1 first.
BACKEND := uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
FRONTEND := npm start -- --host 127.0.0.1 --port 4200
# By port, so that servers started by hand are stopped too; /T includes child processes.
STOP_SERVERS := powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 8000,4200 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { taskkill /F /T /PID $$_.OwningProcess }; exit 0"

.DEFAULT_GOAL := help
.PHONY: help start up stop restart clean test test-backend test-frontend

help:
	@echo make start    database and migrations, then backend and frontend in their own windows
	@echo make up       everything as containers built from the image, on port 8080
	@echo make stop     stop backend, frontend and all containers; data is kept
	@echo make restart  stop, then start
	@echo make clean    stop, then delete the containers and the database data; images are kept
	@echo make test     all tests with coverage reports, against a database of their own

# `cmd /c start`, not `start`: from Git Bash, make would run Git's `start` script.
# No quoted window title: make drops the quotes, and start would open it as a file.
start:
	docker compose up --detach --wait db
	cd backend && uv run alembic upgrade head
	if not exist frontend\node_modules (cd frontend && npm ci)
	cmd /c start /min cmd /c "title backend && cd backend && $(BACKEND)"
	cmd /c start /min cmd /c "title frontend && cd frontend && $(FRONTEND)"
	curl --silent --output nul --retry 60 --retry-delay 2 --retry-all-errors http://127.0.0.1:8000/readyz
	curl --silent --output nul --retry 60 --retry-delay 2 --retry-all-errors http://127.0.0.1:4200
	@echo Backend:  http://localhost:8000/docs
	@echo Frontend: http://localhost:4200

up:
	docker compose --profile app up --build --detach --wait
	@echo Application: http://localhost:8080  (Swagger UI: http://localhost:8080/docs)

stop:
	$(STOP_SERVERS)
	docker compose --profile app --profile test down

restart: stop start

clean:
	$(STOP_SERVERS)
	docker compose --profile app --profile test down --volumes --remove-orphans

# Runs both suites even if one fails, and removes the test database in any case.
test:
	docker compose --profile test up --detach --wait test-db
	$(MAKE) --keep-going --no-print-directory test-backend test-frontend || (docker compose --profile test rm --stop --force test-db & exit 1)
	docker compose --profile test rm --stop --force test-db
	@echo Coverage: backend\htmlcov\index.html and frontend\coverage\frontend\lcov-report\index.html

test-backend: export APP_TEST_DATABASE_URL := postgresql+psycopg://skills:skills@127.0.0.1:5433/skills_test
test-backend:
	cd backend && uv run pytest --cov-report=html --cov-report=xml

test-frontend:
	cd frontend && npm run test:ci
