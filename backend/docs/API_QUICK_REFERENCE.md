# DietGuard Authentication API - Quick Reference

## Base URL
```
http://localhost:8000
```

## 🎁 7-Day Trial Feature

**All new users automatically get a 7-day paid trial!**
- ✅ Unlimited uploads during trial
- ✅ Auto-converts to free tier after 7 days
- ✅ No credit card required

## Authentication Flow

### 1. Sign Up (Gets 7-Day Trial)
```bash
POST /api/v1/auth/signup
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "SecurePass@123",
  "firstName": "John",
  "lastName": "Doe",
  "age": 30,
  "gender": "male"
}

Response: {
  "user": {...},
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer"
}
```

### 2. Check Trial Status
```bash
GET /api/v1/users/me/usage
Authorization: Bearer <token>

Response: {
  "plan_type": "paid",
  "is_trial": true,
  "trial_days_remaining": 6,
  "trial_end_date": "2025-12-22T15:30:00Z",
  "uploads_today": 0,
  "remaining_uploads": -1
}
```

### 3. Sign In
```bash
POST /api/v1/auth/signin
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "SecurePass@123"
}

Response: Same as signup
```

### 4. Use Protected Endpoints
```bash
GET /api/v1/users/me
Authorization: Bearer <access_token>
```

### 5. Refresh Token
```bash
POST /api/v1/auth/refresh-token
Content-Type: application/json

{
  "refresh_token": "eyJ..."
}

Response: {
  "access_token": "new_token...",
  "token_type": "bearer"
}
```

## Subscription Tiers

### 🎁 7-Day Trial (Automatic)
- **Duration**: 7 days from signup
- **Uploads**: Unlimited
- **Auto-converts**: To free tier after expiration

### 🆓 Free Tier (After Trial)
- **Uploads**: 2 per day
- **Reset**: Midnight UTC
- **Cost**: Free forever

### ⭐ Paid Tier
- **Uploads**: Unlimited
- **Cost**: TBD
- **Upgrade**: Via payment API

## Password Requirements
- Minimum 6 characters
- Maximum 1024 bytes (UTF-8)

## Token Expiration
- Access Token: 15 minutes
- Refresh Token: 7 days

## Common Endpoints

### User Management
```bash
# Get profile
GET /api/v1/users/me
Authorization: Bearer <token>

# Check usage & trial status
GET /api/v1/users/me/usage
Authorization: Bearer <token>

# Update profile
PUT /api/v1/users/me
Authorization: Bearer <token>
Content-Type: application/json
{
  "firstName": "Jane",
  "age": 31
}

# Delete account
DELETE /api/v1/users/me
Authorization: Bearer <token>
```

### Food Upload (Protected)
```bash
POST /upload_food/
Authorization: Bearer <token>
Content-Type: multipart/form-data

meal_time=lunch
files=@food.jpg

# During trial: Unlimited uploads
# After trial: 2 uploads per day
```

### Report Upload (Protected)
```bash
POST /upload_report/
Authorization: Bearer <token>
Content-Type: multipart/form-data

files=@report.pdf
```

## Trial Lifecycle

### Day 1-7 (Trial Active)
```json
{
  "plan_type": "paid",
  "is_trial": true,
  "trial_days_remaining": 5,
  "uploads_today": 3,
  "remaining_uploads": -1
}
```

### Day 8+ (Trial Expired)
```json
{
  "plan_type": "free",
  "is_trial": false,
  "uploads_today": 1,
  "remaining_uploads": 1,
  "max_daily_uploads": 2
}
```

## Error Codes

| Code | Meaning |
|------|---------|
| 400 | Bad Request (validation error) |
| 401 | Unauthorized (invalid/expired token) |
| 403 | Forbidden (insufficient permissions) |
| 404 | Not Found |
| 429 | Too Many Requests (upload limit exceeded) |
| 500 | Internal Server Error |

## Environment Setup

### Minimum Required
```bash
# Database
POSTGRES_USER=dietguard
POSTGRES_PASSWORD=your_password
POSTGRES_DB=dietguard

# JWT
JWT_SECRET_KEY=your-secret-key-min-32-chars

# AWS (for AI features)
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
```

## Quick Start

```bash
# 1. Setup environment
cd backend
cp .env.example .env
# Edit .env

# 2. Install dependencies
uv sync

# 3. Run migrations
uv run alembic upgrade head

# 4. Start server
uv run uvicorn main:app --reload

# 5. Test signup (gets 7-day trial)
curl -X POST http://localhost:8000/api/v1/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"Secure@123","firstName":"Test","lastName":"User"}'

# 6. Check trial status
curl http://localhost:8000/api/v1/users/me/usage \
  -H "Authorization: Bearer <token>"
```

## Interactive Documentation
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Tips

1. **Trial Period**: All new users get 7 days of unlimited uploads
2. **Password Length**: Keep passwords under 72 characters (bcrypt limit)
3. **Token Refresh**: Refresh access token before it expires (15 min)
4. **Upload Limits**: Check `/users/me/usage` to see remaining uploads
5. **Trial Countdown**: Monitor `trial_days_remaining` in usage stats
