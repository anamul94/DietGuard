# ProdMeasure

AI-powered product dimension research agent for freight cost calculation.

## Features

- **Intelligent Dimension Search**: Uses AI agents to find exact product dimensions from web sources
- **Multi-Source Research**: Searches manufacturer specs, retailer pages, and technical datasheets
- **Structured Output**: Returns dimensions in standardized format (width, height, depth, unit)
- **Clean Architecture**: Follows domain-driven design principles
- **REST API**: Simple HTTP endpoints for integration

## API Endpoints

### GET /
Health check endpoint
```json
{"message": "Hello from prodmeasure!"}
```

### POST /measure
Get product dimensions by description
```bash
curl -X POST "http://localhost:8000/measure" \
  -H "Content-Type: application/json" \
  -d '{"description": "Dell PowerEdge R760XS Server"}'
```

Response:
```json
{
  "dimensions": {
    "width": 17.09,
    "height": 1.7,
    "depth": 28.5,
    "unit": "inches"
  }
}
```

## Quick Start

### Local Development
```bash
# Install dependencies
make install

# Run locally
make dev
```

### Docker
```bash
# Build image
make build

# Run container
make run

# Stop container
make stop
```

## Environment Setup

Copy `.env.example` to `.env` and fill in your API keys:
```bash
cp .env.example .env
```

Edit `.env` with your credentials:
```env
TAVILY_API_KEY=your_tavily_api_key_here
AWS_ACCESS_KEY_ID=your_aws_access_key_id
AWS_SECRET_ACCESS_KEY=your_aws_secret_access_key
AWS_REGION=us-east-1
```

## Requirements

- Python 3.11+
- UV package manager
- Docker (optional)