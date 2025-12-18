# DietGuard Docker Setup (Simplified)

## Quick Start

### Prerequisites
- Docker and Docker Compose installed
- AWS credentials for LLM access

### Setup

1. **Configure Environment Variables**
   ```bash
   cd backend
   cp .env.example .env
   # Edit .env and add your actual values:
   # - AWS_ACCESS_KEY_ID
   # - AWS_SECRET_ACCESS_KEY
   # - JWT_SECRET_KEY (generate a strong random key)
   # - LANGFUSE keys (optional)
   ```

2. **Start Services**
   ```bash
   cd ..
   docker-compose up -d
   ```

3. **Check Logs**
   ```bash
   # All services
   docker-compose logs -f
   
   # Backend only
   docker-compose logs -f backend
   
   # Database only
   docker-compose logs -f postgres
   ```

4. **Stop Services**
   ```bash
   docker-compose down
   ```

5. **Stop and Remove Data** (⚠️ deletes database)
   ```bash
   docker-compose down -v
   ```

## Services

### PostgreSQL Database
- **Port:** 5432 (host) → 5432 (container)
- **Database:** dietguard_db
- **User:** postgres
- **Password:** postgres123
- **Data:** Persisted in `postgres_data` volume

### Backend API
- **Port:** 8000 (host) → 8000 (container)
- **Auto-migrations:** Runs `alembic upgrade head` on startup
- **Hot-reload:** Enabled for development
- **Health check:** http://localhost:8000/health
- **API docs:** http://localhost:8000/docs

## Database Migrations

### Automatic (on startup)
Migrations run automatically when the backend container starts.

### Manual Migration
```bash
# Create new migration
docker-compose exec backend uv run alembic revision -m "migration_name"

# Run migrations
docker-compose exec backend uv run alembic upgrade head

# Rollback one migration
docker-compose exec backend uv run alembic downgrade -1

# View current version
docker-compose exec backend uv run alembic current

# View history
docker-compose exec backend uv run alembic history
```

## Useful Commands

### Access Database
```bash
# Using docker exec
docker-compose exec postgres psql -U postgres -d dietguard_db

# Using psql from host (if installed)
psql -h localhost -p 5432 -U postgres -d dietguard_db
```

### Rebuild Services
```bash
# Rebuild all
docker-compose up -d --build

# Rebuild backend only
docker-compose up -d --build backend
```

### View Service Status
```bash
docker-compose ps
```

### Clean Up
```bash
# Remove stopped containers
docker-compose rm

# Remove unused images
docker image prune

# Remove everything including volumes (⚠️ deletes data)
docker-compose down -v
docker system prune -a
```

## Troubleshooting

### Database Connection Issues
```bash
# Check if postgres is healthy
docker-compose ps postgres

# Check postgres logs
docker-compose logs postgres

# Restart postgres
docker-compose restart postgres

# Connect to postgres container
docker-compose exec postgres sh
```

### Migration Errors
```bash
# Check current migration version
docker-compose exec backend uv run alembic current

# View migration history
docker-compose exec backend uv run alembic history

# Manually run migrations
docker-compose exec backend uv run alembic upgrade head
```

### Backend Not Starting
```bash
# Check backend logs
docker-compose logs backend

# Check if database is ready
docker-compose exec postgres pg_isready -U postgres

# Restart backend
docker-compose restart backend

# Rebuild backend
docker-compose up -d --build backend
```

### Port Already in Use
```bash
# Check what's using port 8000
lsof -i :8000

# Or use different port in docker-compose.yml
# Change "8000:8000" to "8001:8000"
```

## Development Workflow

1. **Start services**
   ```bash
   docker-compose up -d
   ```

2. **Make code changes** - Backend auto-reloads

3. **Create migration** (if database changes)
   ```bash
   docker-compose exec backend uv run alembic revision -m "description"
   # Edit the migration file
   docker-compose exec backend uv run alembic upgrade head
   ```

4. **View logs**
   ```bash
   docker-compose logs -f backend
   ```

5. **Stop when done**
   ```bash
   docker-compose down
   ```

## Production Deployment

For production, update:
1. Change `POSTGRES_PASSWORD` in docker-compose.yml
2. Set `DEBUG=False` in `.env`
3. Use strong `JWT_SECRET_KEY` (min 32 characters)
4. Remove `--reload` from backend command
5. Configure proper logging
6. Set up SSL/TLS certificates
7. Use production-grade PostgreSQL configuration
8. Set up backups for postgres_data volume
