/**
 * API configuration for the application
 */

import { ENV_CONFIG } from './environment';

export const API_CONFIG = {
  BASE_URL: ENV_CONFIG.API_BASE_URL,
  TIMEOUT: ENV_CONFIG.API_TIMEOUT,
  RETRY_ATTEMPTS: ENV_CONFIG.API_RETRY_ATTEMPTS,
  RETRY_DELAY: ENV_CONFIG.API_RETRY_DELAY
} as const;

export default API_CONFIG;
