.PHONY: help build run stop clean dev install setup-db migrate create-migration test lint format check-outdated upgrade serve logs status reset-db backup-db restore-db

# Variables
IMAGE_NAME = dietguard-backend-food
CONTAINER_NAME = dietguard-backend-app
PORT = 8000
DOCKER_PORT = 8011
UV = UV_CACHE_DIR=/tmp/uv-cache uv

# Default target
help: ## Show this help message
	@echo "DietGuard Backend - Available Commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Development Commands
dev: ## Start development server with hot reload
	$(UV) run uvicorn main:app --reload --host 0.0.0.0 --port $(PORT)

serve: ## Start production server
	$(UV) run uvicorn main:app --host 0.0.0.0 --port $(PORT)

test: ## Run tests
	$(UV) run pytest tests/ -v

test-coverage: ## Run tests with coverage report
	$(UV) run pytest tests/ -v --cov=src --cov-report=html --cov-report=term

lint: ## Run linting checks
	$(UV) run ruff check src/

format: ## Format code
	$(UV) run ruff format src/

format-check: ## Check code formatting without making changes
	$(UV) run ruff format --check src/

# Package Management
install: ## Install dependencies
	$(UV) sync

upgrade: ## Upgrade all packages to latest versions
	$(UV) sync --upgrade

check-outdated: ## Check for outdated packages
	$(UV) tree --outdated

# Database Commands
setup-db: ## Setup database (run initial setup script)
	./scripts/setup_tables.sh

full-setup: ## Complete database setup (setup + migrate + seed)
	@echo "🚀 Starting complete database setup..."
	make setup-db
	@echo "📊 Running migrations..."
	make migrate
	@echo "🌱 Seeding initial data..."
	make seed-data
	@echo "✅ Database setup complete!"

migrate: ## Run database migrations
	$(UV) run alembic upgrade head

force-migrate: ## Force run migrations (downgrade and upgrade)
	@echo "⚠️  Force migrating database..."
	$(UV) run alembic downgrade -1
	$(UV) run alembic upgrade head
	@echo "✅ Force migration complete!"

create-migration: ## Create a new migration (usage: make create-migration MSG="description")
	@if [ -z "$(MSG)" ]; then \
		echo "Error: Please provide a message. Usage: make create-migration MSG='your description'"; \
		exit 1; \
	fi
	$(UV) run python create_migration.py "$(MSG)"

migration-history: ## Show migration history
	$(UV) run alembic history

migration-current: ## Show current migration
	$(UV) run alembic current

migration-heads: ## Show migration heads
	$(UV) run alembic heads

reset-db: ## Reset database (WARNING: This will drop all data)
	@echo "WARNING: This will drop all database data!"
	@read -p "Are you sure? (y/N): " confirm && [ "$$confirm" = "y" ] || exit 1
	$(UV) run alembic downgrade base
	$(UV) run alembic upgrade head

db-health: ## Check database health and migration status
	@echo "🏥 Database Health Check"
	@echo "======================"
	@echo "📊 Current Migration:"
	@make migration-current
	@echo ""
	@echo "🎯 Migration Heads:"
	@make migration-heads
	@echo ""
	@echo "🔍 Environment Check:"
	@make check-env
	@echo ""
	@echo "✅ Database health check complete!"

backup-db: ## Backup database to file
	@echo "Creating database backup..."
	pg_dump $(DATABASE_URL) > backup_$(shell date +%Y%m%d_%H%M%S).sql
	restore-db: ## Restore database from backup file (usage: make restore-db FILE=backup.sql)
	@if [ -z "$(FILE)" ]; then \
		echo "Error: Please provide backup file. Usage: make restore-db FILE=backup.sql"; \
		exit 1; \
	fi
	psql $(DATABASE_URL) < $(FILE)

# Docker Commands
build: ## Build Docker image
	docker build -t $(IMAGE_NAME) .

run: ## Run Docker container
	docker run -d --name $(CONTAINER_NAME) -p $(DOCKER_PORT):$(PORT) --env-file .env $(IMAGE_NAME)

stop: ## Stop and remove Docker container
	@if docker ps -q -f name=$(CONTAINER_NAME) | grep -q .; then \
		docker stop $(CONTAINER_NAME); \
	fi
	@if docker ps -aq -f name=$(CONTAINER_NAME) | grep -q .; then \
		docker rm $(CONTAINER_NAME); \
	fi

restart: stop run ## Restart Docker container

logs: ## Show Docker container logs
	docker logs -f $(CONTAINER_NAME)

status: ## Show Docker container status
	docker ps -f name=$(CONTAINER_NAME)

clean: ## Remove Docker image
	@if docker images -q $(IMAGE_NAME) | grep -q .; then \
		docker rmi $(IMAGE_NAME); \
	fi

clean-all: stop clean ## Stop container and remove image

# Utility Commands
check-env: ## Check if required environment variables are set
	@echo "Checking environment variables..."
	@$(UV) run python -c "from src.infrastructure.config.settings import settings; print('✓ Environment configuration loaded successfully')"

test-model: ## Test the AI model configuration
	$(UV) run python test_model.py

generate-key: ## Generate new encryption key
	$(UV) run python scripts/generate_encryption_key.py

seed-data: ## Seed database with initial data
	$(UV) run python scripts/seed_roles.py
	$(UV) run python scripts/seed_packages.py

validate: ## Run all validation checks
	make format-check
	make lint
	make test
	make check-env

# Quick shortcuts
up: dev ## Alias for dev
down: stop ## Alias for stop
reload: restart ## Alias for restart
