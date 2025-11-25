/**
 * Logging Configuration
 * 
 * Centralized configuration for the logging system
 */

import { LogLevel } from '../utils/logger';

export interface LoggingConfig {
  // Log level configuration
  level: LogLevel;

  // Enable/disable logging
  enabled: boolean;

  // Console logging
  consoleEnabled: boolean;

  // Remote logging (for future CloudWatch integration)
  remoteEnabled: boolean;
  remoteEndpoint?: string;

  // Sampling rate (0-1, where 1 = log everything, 0.1 = log 10%)
  samplingRate: number;

  // Batch size for remote logging
  batchSize: number;

  // Flush interval in milliseconds
  flushInterval: number;

  // Sensitive data patterns to redact
  redactPatterns: RegExp[];
}

/**
 * Get logging configuration based on environment
 */
export function getLoggingConfig(): LoggingConfig {
  const env = process.env.NODE_ENV;
  const isProduction = env === 'production';

  return {
    // Log level
    level: isProduction ? LogLevel.ERROR : LogLevel.DEBUG,

    // Enable logging
    enabled: true,

    // Console logging
    consoleEnabled: true,

    // Remote logging (disabled by default, can be enabled later)
    remoteEnabled: false,
    remoteEndpoint: process.env.REACT_APP_LOG_ENDPOINT,

    // Sampling (100% in dev, 10% in production for non-error logs)
    samplingRate: isProduction ? 0.1 : 1.0,

    // Batch configuration
    batchSize: 10,
    flushInterval: 5000, // 5 seconds

    // Redact sensitive data (mobile numbers, emails, tokens)
    redactPatterns: [
      /\b\d{10,}\b/g, // Phone numbers
      /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b/g, // Emails
      /Bearer\s+[A-Za-z0-9\-._~+\/]+=*/g, // Bearer tokens
      /password["\s:=]+[^\s"]+/gi, // Passwords
    ],
  };
}

export const loggingConfig = getLoggingConfig();
