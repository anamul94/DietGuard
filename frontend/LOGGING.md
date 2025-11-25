# Frontend Logging System

## Quick Start

```typescript
import { logger } from './utils/logger';

// Basic logging
logger.info('User logged in', { userId: '123' });
logger.error('Login failed', error, { username: 'user@example.com' });

// Performance tracking
const timer = logger.startTimer('api-call');
await fetchData();
timer.done('Data fetched successfully');

// Set user context (persists across all logs)
logger.setContext({ userId: '123', sessionId: 'abc' });
```

## Features

- ✅ Structured logging with metadata
- ✅ Error tracking with stack traces
- ✅ Performance monitoring with timers
- ✅ Context management (user session, request IDs)
- ✅ Environment-based log level filtering
- ✅ Colored console output for development
- ✅ Extensible transport layer for remote logging
- ✅ Error Boundary for catching unhandled React errors

## Log Levels

- **DEBUG**: Detailed information for debugging (dev only)
- **INFO**: General informational messages
- **WARN**: Warning messages
- **ERROR**: Error messages (always logged)

## Configuration

Edit `src/config/logging.config.ts` to customize:
- Log levels per environment
- Sampling rates
- Sensitive data redaction patterns
- Remote logging endpoints

## Environment Variables

```bash
# Set log level (optional, defaults to DEBUG in dev, ERROR in production)
REACT_APP_LOG_LEVEL=DEBUG

# Remote logging endpoint (optional, for CloudWatch integration)
REACT_APP_LOG_ENDPOINT=https://api.example.com/logs
```

## Best Practices

1. **Use appropriate log levels**: DEBUG for details, INFO for events, ERROR for failures
2. **Include metadata**: Always provide context with your logs
3. **Set user context**: Call `logger.setContext()` at login
4. **Use timers**: Track performance of slow operations
5. **Log errors properly**: Pass Error objects, not strings

## Examples

### API Call Logging

```typescript
try {
  logger.info('Fetching user data', { userId });
  const data = await api.getUser(userId);
  logger.info('User data fetched', { userId, dataSize: data.length });
  return data;
} catch (error) {
  logger.error('Failed to fetch user data', error, { userId });
  throw error;
}
```

### Performance Monitoring

```typescript
const timer = logger.startTimer('image-upload');
await uploadImage(file);
timer.done('Image uploaded', { fileSize: file.size });
```

### Context Management

```typescript
// Set once at login
logger.setContext({ 
  userId: user.id, 
  sessionId: session.id,
  userRole: user.role 
});

// All subsequent logs automatically include this context
logger.info('User action'); // Includes userId, sessionId, userRole
```

## CloudWatch Integration (Future)

The logger is designed to support CloudWatch Logs integration. To add:

1. Create backend endpoint `/api/logs`
2. Implement CloudWatch transport
3. Add transport to logger: `logger.addTransport(new CloudWatchTransport())`

See `walkthrough.md` for detailed implementation guide.
