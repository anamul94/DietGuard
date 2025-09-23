# DietGuard AI - AI-Powered Nutritionist

An AI-powered nutritionist application that analyzes medical reports and food images to provide personalized dietary recommendations.

## Features

- 🏥 **Medical Report Analysis** - Upload medical reports for AI analysis by Dr. Maria Chen
- 🍎 **Food Analysis** - Upload food images for nutritional analysis by Dr. James Rodriguez
- 👩‍⚕️ **Nutritionist Recommendations** - Get personalized advice from Dr. Sarah Mitchell
- 📱 **QR Code Support** - Mobile-friendly food upload via QR code
- 🔒 **Privacy First** - Data automatically deleted after 24 hours
- 📊 **Professional Reports** - EHR-compatible medical analysis

## Quick Start with Docker

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd DietGuard
   ```

2. **Start the application**
   ```bash
   docker-compose up -d
   ```

3. **Access the application**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - Redis: localhost:6379

## Manual Setup

### Backend Setup
```bash
cd backend
uv sync
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

### Backend (.env)
```
AWS_ACCESS_KEY_ID=your_aws_key
AWS_SECRET_ACCESS_KEY=your_aws_secret
AWS_REGION=ap-south-1
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=myredissecret
```

### Frontend (.env)
```
REACT_APP_API_URL=http://localhost:8000
REACT_APP_DOMAIN=localhost:3000
```

## API Endpoints

- `POST /upload_report/` - Upload medical reports
- `POST /upload_food/` - Upload food images
- `GET /get_report/{user_id}` - Get report data
- `GET /get_nutrition/{user_id}` - Get nutrition data
- `DELETE /delete_report/{user_id}` - Delete user data

## Architecture

- **Frontend**: React + TypeScript + Tailwind CSS
- **Backend**: FastAPI + Python
- **AI Agents**: AWS Bedrock (Claude 3 Haiku)
- **Cache**: Redis
- **Deployment**: Docker Compose

## Privacy & Security

- All data is automatically deleted after 24 hours
- No permanent storage of personal information
- Medical-grade security standards
- Manual data deletion available anytime