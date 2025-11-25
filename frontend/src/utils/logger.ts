/**
 * Enhanced Logger Utility for DietGuard Frontend
 * 
 * Features:
 * - Structured logging with metadata
 * - Error tracking with stack traces
 * - Performance monitoring
 * - Context management (user session, request IDs)
 * - Environment-based log level filtering
 * - Extensible transport layer for remote logging
 */

export enum LogLevel {
  ERROR = 0,
  WARN = 1,
  INFO = 2,
  DEBUG = 3,
}

export interface LogMetadata {
  [key: string]: any;
}

export interface LogContext {
  userId?: string;
  sessionId?: string;
  requestId?: string;
  component?: string;
  [key: string]: any;
}

export interface LogEntry {
  timestamp: string;
  level: LogLevel;
  levelName: string;
  message: string;
  metadata?: LogMetadata;
  context?: LogContext;
  error?: {
    name: string;
    message: string;
    stack?: string;
  };
}

export interface LogTransport {
  log(entry: LogEntry): void;
}

/**
 * Console transport with colored output for development
 */
class ConsoleTransport implements LogTransport {
  private colors = {
    [LogLevel.ERROR]: '\x1b[31m', // Red
    [LogLevel.WARN]: '\x1b[33m',  // Yellow
    [LogLevel.INFO]: '\x1b[36m',  // Cyan
    [LogLevel.DEBUG]: '\x1b[90m', // Gray
  };
  private reset = '\x1b[0m';

  log(entry: LogEntry): void {
    const color = this.colors[entry.level] || '';
    const prefix = `${color}[${entry.timestamp}] ${entry.levelName}${this.reset}`;
    
    const parts: any[] = [prefix, entry.message];
    
    // Add context if present
    if (entry.context && Object.keys(entry.context).length > 0) {
      parts.push('\n  Context:', entry.context);
    }
    
    // Add metadata if present
    if (entry.metadata && Object.keys(entry.metadata).length > 0) {
      parts.push('\n  Metadata:', entry.metadata);
    }
    
    // Add error details if present
    if (entry.error) {
      parts.push('\n  Error:', entry.error);
    }
    
    // Use appropriate console method
    const consoleMethod = entry.level === LogLevel.ERROR ? console.error :
                         entry.level === LogLevel.WARN ? console.warn :
                         console.log;
    
    consoleMethod(...parts);
  }
}

/**
 * Performance timer for measuring operation duration
 */
export class PerformanceTimer {
  private startTime: number;
  private label: string;
  private logger: Logger;

  constructor(label: string, logger: Logger) {
    this.label = label;
    this.logger = logger;
    this.startTime = performance.now();
  }

  /**
   * Complete the timer and log the duration
   */
  done(message?: string, metadata?: LogMetadata): void {
    const duration = performance.now() - this.startTime;
    const logMessage = message || `${this.label} completed`;
    
    this.logger.info(logMessage, {
      ...metadata,
      duration: `${duration.toFixed(2)}ms`,
      label: this.label,
    });
  }
}

/**
 * Main Logger class
 */
class Logger {
  private level: LogLevel;
  private transports: LogTransport[] = [];
  private context: LogContext = {};
  private enabled: boolean = true;

  constructor() {
    // Set log level based on environment
    this.level = this.getLogLevelFromEnv();
    
    // Add console transport by default
    this.transports.push(new ConsoleTransport());
  }

  /**
   * Get log level from environment
   */
  private getLogLevelFromEnv(): LogLevel {
    const env = process.env.NODE_ENV;
    const configLevel = process.env.REACT_APP_LOG_LEVEL;
    
    if (configLevel) {
      const level = LogLevel[configLevel.toUpperCase() as keyof typeof LogLevel];
      if (level !== undefined) return level;
    }
    
    // Default levels by environment
    return env === 'production' ? LogLevel.ERROR : LogLevel.DEBUG;
  }

  /**
   * Set global context that will be included in all logs
   */
  setContext(context: LogContext): void {
    this.context = { ...this.context, ...context };
  }

  /**
   * Clear specific context keys or all context
   */
  clearContext(keys?: string[]): void {
    if (!keys) {
      this.context = {};
    } else {
      keys.forEach(key => delete this.context[key]);
    }
  }

  /**
   * Get current context
   */
  getContext(): LogContext {
    return { ...this.context };
  }

  /**
   * Add a custom transport
   */
  addTransport(transport: LogTransport): void {
    this.transports.push(transport);
  }

  /**
   * Enable or disable logging
   */
  setEnabled(enabled: boolean): void {
    this.enabled = enabled;
  }

  /**
   * Set log level dynamically
   */
  setLevel(level: LogLevel): void {
    this.level = level;
  }

  /**
   * Core logging method
   */
  private log(
    level: LogLevel,
    message: string,
    metadataOrError?: LogMetadata | Error,
    additionalMetadata?: LogMetadata
  ): void {
    if (!this.enabled || level > this.level) {
      return;
    }

    const entry: LogEntry = {
      timestamp: new Date().toISOString(),
      level,
      levelName: LogLevel[level],
      message,
      context: Object.keys(this.context).length > 0 ? { ...this.context } : undefined,
    };

    // Handle error parameter
    if (metadataOrError instanceof Error) {
      entry.error = {
        name: metadataOrError.name,
        message: metadataOrError.message,
        stack: metadataOrError.stack,
      };
      if (additionalMetadata) {
        entry.metadata = additionalMetadata;
      }
    } else if (metadataOrError) {
      entry.metadata = metadataOrError;
    }

    // Send to all transports
    this.transports.forEach(transport => {
      try {
        transport.log(entry);
      } catch (err) {
        // Prevent logging errors from breaking the application
        console.error('Logger transport error:', err);
      }
    });
  }

  /**
   * Log error message
   */
  error(message: string, error?: Error | LogMetadata, metadata?: LogMetadata): void {
    this.log(LogLevel.ERROR, message, error, metadata);
  }

  /**
   * Log warning message
   */
  warn(message: string, metadata?: LogMetadata): void {
    this.log(LogLevel.WARN, message, metadata);
  }

  /**
   * Log info message
   */
  info(message: string, metadata?: LogMetadata): void {
    this.log(LogLevel.INFO, message, metadata);
  }

  /**
   * Log debug message
   */
  debug(message: string, metadata?: LogMetadata): void {
    this.log(LogLevel.DEBUG, message, metadata);
  }

  /**
   * Start a performance timer
   */
  startTimer(label: string): PerformanceTimer {
    return new PerformanceTimer(label, this);
  }

  /**
   * Create a child logger with additional context
   */
  child(context: LogContext): Logger {
    const childLogger = new Logger();
    childLogger.level = this.level;
    childLogger.transports = [...this.transports];
    childLogger.context = { ...this.context, ...context };
    childLogger.enabled = this.enabled;
    return childLogger;
  }
}

// Export singleton instance
export const logger = new Logger();

// Export types and classes for advanced usage
export { Logger, ConsoleTransport };