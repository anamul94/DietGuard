.PHONY: help up down build restart logs shell db-shell migrate seed clean

# Default target
help:
	@echo "DietGuard Makefile Commands:"
	@echo ""
	@echo "  make up          - Start all services"
	@echo "  make down        - Stop all services"
	@echo "  make build       - Build and start services"
	@echo "  make restart     - Restart all services"
	@echo "  make logs        - View logs (all services)"
	@echo "  make logs-backend - View backend logs only"
	@echo "  make logs-db     - View database logs only"
	@echo ""
	@echo "  make shell       - Access backend container shell"
	@echo "  make db-shell    - Access PostgreSQL shell"
	@echo ""
	@echo "  make migrate     - Run database migrations"
	@echo "  make seed        - Seed subscription packages"
	@echo "  make setup       - Complete setup (build + migrate + seed)"
	@echo ""
	@echo "  make clean       - Stop and remove all containers and volumes"
	@echo "  make clean-orphans - Remove orphan containers"
	@echo ""
	@echo "  make status      - Show container status"
	@echo "  make health      - Check API health"

# Start services
up:
	docker compose up -d

# Stop services
down:
	docker compose down

# Build and start services
build:
	docker compose up --build -d

# Restart services
restart:
	docker compose restart

# View logs
logs:
	docker compose logs -f

logs-backend:
	docker compose logs -f backend

logs-db:
	docker compose logs -f postgres

# Access shells
shell:
	docker compose exec backend sh

db-shell:
	docker compose exec postgres psql -U postgres -d dietguard_db

# Database operations
migrate:
	@echo "Running database migrations..."
	docker compose exec backend uv run alembic upgrade head
	@echo "✓ Migrations completed"

seed:
	@echo "Seeding subscription packages..."
	docker compose exec backend uv run python scripts/seed_packages.py
	@echo "✓ Seeding completed"

# Complete setup
setup: build
	@echo "Waiting for services to be ready..."
	@sleep 8
	@echo "Running migrations..."
	@$(MAKE) migrate
	@echo "Seeding database..."
	@$(MAKE) seed
	@echo ""
	@echo "✓ Setup complete!"
	@echo "  Backend API: http://localhost:8000"
	@echo "  API Docs: http://localhost:8000/docs"
	@echo ""

# Cleanup
clean:
	@echo "⚠️  This will remove all containers and volumes (including data)"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		docker compose down -v; \
		echo "✓ Cleanup complete"; \
	else \
		echo "Cancelled"; \
	fi

clean-orphans:
	docker compose down --remove-orphans

# Status and health
status:
	docker compose ps

health:
	@echo "Checking API health..."
	@curl -s http://localhost:8000/health | python3 -m json.tool || echo "❌ API not responding"
