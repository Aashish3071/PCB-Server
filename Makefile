.PHONY: start-backend start-simulator start-frontend test-backend test-simulator test-frontend test-all format-python format-frontend lint migrate reset-db seed export-logs docs

start-backend:
	@echo "Starting Backend..."
	cd backend && uv run uvicorn app.main:app --reload

start-simulator:
	@echo "Starting Simulator..."
	cd simulator && uv run python main.py --config config/development.yaml

start-frontend:
	@echo "Starting Frontend..."
	cd frontend && npm run dev

test-backend:
	@echo "Running Backend Tests..."
	cd backend && uv run pytest

test-simulator:
	@echo "Running Simulator Tests..."
	cd simulator && uv run pytest

test-frontend:
	@echo "Running Frontend Tests..."
	cd frontend && npm test

test-all: test-backend test-simulator test-frontend

format-python:
	@echo "Formatting Python Code..."
	cd backend && uv run ruff format .
	cd simulator && uv run ruff format .

format-frontend:
	@echo "Formatting Frontend Code..."
	cd frontend && npm run format

lint:
	@echo "Running Linters..."
	cd backend && uv run ruff check .
	cd simulator && uv run ruff check .
	cd frontend && npm run lint

migrate:
	@echo "Applying Database Migrations..."
	cd backend && uv run alembic upgrade head

reset-db:
	@echo "Resetting Development Database..."
	# Implementation specific to project reset

seed:
	@echo "Seeding Sample Data..."
	# Implementation specific to project seed

export-logs:
	@echo "Exporting Logs..."
	# Implement log export

docs:
	@echo "Building Documentation..."
	# Implement docs build
