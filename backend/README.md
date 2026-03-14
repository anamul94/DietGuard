# DietGuard AI - AI-Powered Nutritionist with Authentication

An AI-powered nutritionist application with comprehensive authentication, role-based access control, and subscription management. Analyzes medical reports and food images to provide personalized dietary recommendations.

## Features

### Core Features
- 🏥 **Medical Report Analysis** - Upload medical reports for AI analysis
- 🍎 **Food Analysis** - Upload food images for nutritional analysis
- 👩‍⚕️ **Nutritionist Recommendations** - Get personalized dietary advice
- 📱 **QR Code Support** - Mobile-friendly food upload via QR code

### Authentication & Security
- 🔐 **JWT Authentication** - Secure token-based authentication
- 👥 **Role-Based Access Control** - User and Admin roles
- 🔑 **Password Management** - Secure password reset flow
- 📊 **Audit Logging** - Comprehensive security event tracking
- 🛡️ **GDPR Compliance** - User data deletion support

### Subscription Management
- 💳 **Free Tier** - 2 food uploads per day
- ⭐ **Paid Tier** - Unlimited uploads
- 📈 **Usage Tracking** - Real-time upload limit monitoring

## Quick Start with Docker

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd DietGuard
   ```

2. **Configure environment**
   ```bash
   cd backend
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Start the application**
   ```bash
   docker-compose up -d
   ```

4. **Run database migrations**
   ```bash
   docker exec -it dietguard-backend uv run alembic upgrade head
   ```

5. **Access the application**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Docs: http://localhost:8000/docs
   - Redis: localhost:6379

## Manual Setup

### Prerequisites
- Python 3.11+
- PostgreSQL 14+
- Redis 7+
- Node.js 18+ (for frontend)

### Backend Setup

1. **Install dependencies**
   ```bash
   cd backend
   uv sync
   ```

2. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Setup database**
   ```bash
   # Create PostgreSQL database
   createdb dietguard
   
   # Run migrations
   uv run alembic upgrade head
   ```

4. **Start the server**
   ```bash
   uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

### Frontend Setup
```bash
cd frontend
npm install
npm start
```

### Redis Setup
```bash
docker run -d -p 6379:6379 --name redis redis:7-alpine redis-server --requirepass myredissecret
```

## Environment Variables

### Required Variables

```bash
# Database
POSTGRES_USER=dietguard
POSTGRES_PASSWORD=your_secure_password
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=dietguard

# JWT
JWT_SECRET_KEY=your-super-secret-jwt-key
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# AWS
AWS_ACCESS_KEY_ID=your_aws_key
AWS_SECRET_ACCESS_KEY=your_aws_secret
AWS_REGION=ap-south-1

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=myredissecret
```

See `.env.example` for complete configuration options.

## API Endpoints

Canonical API prefix:

- `/api/v1`

Primary endpoint groups:

- Authentication: `/api/v1/auth/*`
- AI analysis: `/api/v1/ai/*`
- Health timeline: `/api/v1/health/*`
- Users: `/api/v1/users/*`
- Packages: `/api/v1/packages/*`
- Payments: `/api/v1/payment*`
- Admin: `/api/v1/admin/*`

Key current endpoints:

- `POST /api/v1/ai/upload-food`
- `POST /api/v1/ai/upload-report`
- `POST /api/v1/ai/nutrition-advice`
- `POST /api/v1/ai/calculate-nutrition`
- `GET /api/v1/health/profile/current`
- `POST /api/v1/health/meals/draft-from-image`
- `POST /api/v1/health/meals/confirm`
- `GET /api/v1/health/meals/today-summary`
- `GET /api/v1/health/meals/history`
- `POST /api/v1/health/vitals`
- `GET /api/v1/health/insights/daily`
- `GET /api/v1/health/insights/weekly`
- `GET /api/v1/health/insights/monthly`

Detailed reference:

- Repository doc: `../docs/api-reference.md`
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## API Documentation

Interactive API documentation is available at:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Repository API Reference**: `../docs/api-reference.md`

## Architecture

- **Frontend**: React + TypeScript + Tailwind CSS
- **Backend**: FastAPI + Python 3.11
- **Database**: PostgreSQL 14+ with SQLAlchemy ORM
- **Authentication**: JWT with Argon2 password hashing
- **AI Agents**: AWS Bedrock (Claude 3 Haiku)
- **Cache**: Redis
- **Deployment**: Docker Compose

## Database Schema

The application uses the following main tables:
- `users` - User accounts
- `roles` - User roles (user, admin)
- `user_roles` - User-role assignments
- `subscriptions` - User subscription plans
- `payments` - Payment records
- `upload_limits` - Daily upload tracking
- `audit_logs` - Security audit trail
- `password_resets` - Password reset tokens
- `report_data` - Medical report data
- `nutrition_data` - Food analysis data

## Security Features

### Password Requirements
- Minimum 8 characters
- At least one uppercase letter
- At least one lowercase letter
- At least one digit
- At least one special character

### Token Expiration
- Access tokens: 15 minutes
- Refresh tokens: 7 days
- Password reset tokens: 1 hour

### Rate Limiting
- Login attempts: 5 per 15 minutes per IP

## Subscription Tiers

### Free Tier
- 2 food image uploads per day
- Resets at midnight UTC
- Full access to medical report analysis

### Paid Tier
- Unlimited food image uploads
- Priority support
- Advanced analytics (coming soon)

## Development

### Running Tests
```bash
cd backend
uv run pytest tests/ -v
```

### Creating Database Migrations
```bash
cd backend
uv run python create_migration.py "description_of_changes"
```

### Applying Migrations
```bash
uv run alembic upgrade head
```

### Rolling Back Migrations
```bash
uv run alembic downgrade -1
```

## Privacy & Security

- JWT-based authentication with secure token storage
- Passwords hashed with Argon2
- Soft delete for user accounts (GDPR compliance)
- Comprehensive audit logging
- Medical-grade security standards
- Manual data deletion available anytime

## Troubleshooting

### Database Connection Issues
```bash
# Check PostgreSQL is running
pg_isready -h localhost -p 5432

# Verify credentials in .env match database
```

### Migration Issues
```bash
# Check current migration status
uv run alembic current

# View migration history
uv run alembic history
```

### Authentication Issues
```bash
# Verify JWT_SECRET_KEY is set in .env
# Check token expiration settings
# Review audit logs for failed attempts
```

## License

[Your License Here]

## Support

For issues and questions, please open an issue on GitHub or contact support@dietguard.com
