/**
 * Environment configuration for the frontend application
 */

export const ENV_CONFIG = {
  // API Configuration
  API_BASE_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  FRONTEND_URL: process.env.NEXT_PUBLIC_FRONTEND_URL || 'http://localhost:3000',
  
  // Environment
  NODE_ENV: process.env.NODE_ENV || 'development',
  IS_DEVELOPMENT: process.env.NODE_ENV === 'development',
  IS_PRODUCTION: process.env.NODE_ENV === 'production',
  
  // File serving URLs
  UPLOADS_URL: process.env.NEXT_PUBLIC_UPLOADS_URL || 'http://localhost:8000/uploads',
  OUTPUT_URL: process.env.NEXT_PUBLIC_OUTPUT_URL || 'http://localhost:8000/output',
  GENERATED_IMAGES_URL: process.env.NEXT_PUBLIC_GENERATED_IMAGES_URL || 'http://localhost:8000/generated_images',
  
  // API Configuration
  API_TIMEOUT: parseInt(process.env.NEXT_PUBLIC_API_TIMEOUT || '10000'),
  API_RETRY_ATTEMPTS: parseInt(process.env.NEXT_PUBLIC_API_RETRY_ATTEMPTS || '3'),
  API_RETRY_DELAY: parseInt(process.env.NEXT_PUBLIC_API_RETRY_DELAY || '1000'),
} as const;

/**
 * Get the full URL for a file path
 */
export const getFileUrl = (path: string, type: 'uploads' | 'output' | 'generated_images' = 'uploads'): string => {
  const baseUrl = {
    uploads: ENV_CONFIG.UPLOADS_URL,
    output: ENV_CONFIG.OUTPUT_URL,
    generated_images: ENV_CONFIG.GENERATED_IMAGES_URL,
  }[type];
  
  // Remove leading slash from path if present
  const cleanPath = path.startsWith('/') ? path.slice(1) : path;
  
  return `${baseUrl}/${cleanPath}`;
};

/**
 * Get API endpoint URL with improved production routing
 */
export const getApiUrl = (endpoint: string): string => {
  // Remove leading slash from endpoint if present
  const cleanEndpoint = endpoint.startsWith('/') ? endpoint.slice(1) : endpoint;
  
  // Auto-detect environment based on hostname
  if (typeof window !== 'undefined') {
    const hostname = window.location.hostname;
    
    // Local development environment
    if (hostname === 'localhost' || hostname === '127.0.0.1') {
      return `http://localhost:8000/${cleanEndpoint}`;
    }
    
    // Production environment - use relative URLs with /api prefix
    // This routes through ALB to the backend service
    return `/api/${cleanEndpoint}`;
  }
  
  // Server-side rendering fallback
  if (ENV_CONFIG.IS_PRODUCTION) {
    // In production SSR, use /api prefix for ALB routing
    return `/api/${cleanEndpoint}`;
  }
  
  // Development fallback - use configured base URL
  return `${ENV_CONFIG.API_BASE_URL}/${cleanEndpoint}`;
};


export default ENV_CONFIG;
