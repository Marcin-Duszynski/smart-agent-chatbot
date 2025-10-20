/**
 * Development-only logging utilities with network request tracing
 */

const isDevelopment = process.env.NODE_ENV === 'development';
const enableNetworkLogs =
  isDevelopment &&
  (process.env.NEXT_PUBLIC_ENABLE_NETWORK_LOGS !== 'false');

/**
 * Colour codes for console output
 */
const colours = {
  reset: '\x1b[0m',
  bright: '\x1b[1m',
  dim: '\x1b[2m',
  blue: '\x1b[34m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  red: '\x1b[31m',
  cyan: '\x1b[36m',
  magenta: '\x1b[35m',
} as const;

export const logger = {
  log: (...args: any[]) => {
    if (isDevelopment) {
      console.log(...args);
    }
  },

  warn: (...args: any[]) => {
    if (isDevelopment) {
      console.warn(...args);
    }
  },

  error: (...args: any[]) => {
    if (isDevelopment) {
      console.error(...args);
    }
  },

  debug: (...args: any[]) => {
    if (isDevelopment) {
      console.debug(...args);
    }
  },

  info: (...args: any[]) => {
    if (isDevelopment) {
      console.info(...args);
    }
  },

  /**
   * Network request logging
   */
  network: (method: string, url: string, metadata?: Record<string, any>) => {
    if (!enableNetworkLogs) return;

    const timestamp = new Date().toLocaleTimeString();
    const methodColour =
      method === 'GET' ? colours.cyan :
      method === 'POST' ? colours.green :
      method === 'PUT' ? colours.yellow :
      method === 'DELETE' ? colours.red :
      colours.reset;

    console.log(
      `${colours.dim}[${timestamp}]${colours.reset} ` +
      `${colours.bright}${methodColour}${method}${colours.reset} ` +
      `${colours.blue}${url}${colours.reset}`,
      metadata ? `${colours.dim}→${colours.reset}` : '',
      metadata || ''
    );
  },

  /**
   * API response logging
   */
  apiResponse: (status: number, url: string, duration?: number) => {
    if (!enableNetworkLogs) return;

    const statusColour =
      status < 300 ? colours.green :
      status < 400 ? colours.yellow :
      colours.red;

    const durationStr = duration ? ` ${colours.dim}(${duration}ms)${colours.reset}` : '';
    console.log(
      `${colours.bright}${statusColour}↳ ${status}${colours.reset} ` +
      `${colours.blue}${url}${colours.reset}` +
      durationStr
    );
  },

  /**
   * SSE event logging
   */
  streamEvent: (eventType: string, data?: any) => {
    if (!enableNetworkLogs) return;

    const eventColour = colours.magenta;
    const timestamp = new Date().toLocaleTimeString();

    console.log(
      `${colours.dim}[${timestamp}]${colours.reset} ` +
      `${colours.bright}${eventColour}📨 EVENT${colours.reset} ` +
      `${eventColour}${eventType}${colours.reset}`,
      data ? `→ ${colours.dim}` : '',
      data || ''
    );
  },

  /**
   * API client logging
   */
  api: (action: string, details?: Record<string, any>) => {
    if (!enableNetworkLogs) return;

    const timestamp = new Date().toLocaleTimeString();
    console.log(
      `${colours.dim}[${timestamp}]${colours.reset} ` +
      `${colours.bright}${colours.cyan}🔌 API${colours.reset} ` +
      `${action}`,
      details ? `→ ${colours.dim}` : '',
      details || ''
    );
  },

  /**
   * Performance timing logging
   */
  timing: (label: string, duration: number) => {
    if (!enableNetworkLogs) return;

    const colour = duration > 1000 ? colours.yellow : colours.cyan;
    console.log(
      `${colours.dim}⏱️  ${label}: ${colour}${duration}ms${colours.reset}`
    );
  }
};

export default logger;