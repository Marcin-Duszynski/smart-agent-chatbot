/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  async headers() {
    // Get allowed origins from environment variable (same as backend CORS_ORIGINS)
    // This ensures consistent security policy between frontend CSP and backend CORS
    const corsOrigins = process.env.CORS_ORIGINS || process.env.NEXT_PUBLIC_CORS_ORIGINS || 'http://localhost:3000';
    
    // Extract full origins from CORS configuration for CSP frame-ancestors
    // We use full origins (protocol + domain + port) for more precise control
    const allowedOrigins = corsOrigins
      .split(',')
      .map(origin => {
        try {
          const url = new URL(origin.trim());
          return url.origin;
        } catch {
          // If parsing fails, skip this origin
          console.warn(`Invalid CORS origin format: ${origin}`);
          return null;
        }
      })
      .filter(Boolean)
      .join(' ');
    
    // Build CSP frame-ancestors directive
    // 'self' allows same-origin embedding, then add configured origins
    const frameAncestors = allowedOrigins 
      ? `frame-ancestors 'self' ${allowedOrigins}`
      : "frame-ancestors 'self'";

    console.log(`CSP frame-ancestors: ${frameAncestors}`);

    return [
      {
        // Apply iframe-friendly headers to the embed route
        source: '/embed',
        headers: [
          {
            key: 'X-Frame-Options',
            value: 'SAMEORIGIN', // Allow embedding from same origin, will be overridden by CSP
          },
          {
            key: 'Content-Security-Policy',
            value: frameAncestors,
          },
        ],
      },
    ];
  },
  async rewrites() {
    const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

    return [
      {
        source: '/api/charts/:path*',
        destination: `${apiBaseUrl}/charts/:path*`
      },
      {
        source: '/api/files/:path*',
        destination: `${apiBaseUrl}/files/:path*`
      },
      {
        source: '/output/:path*',
        destination: `${apiBaseUrl}/output/:path*`
      },
      {
        source: '/uploads/:path*',
        destination: `${apiBaseUrl}/uploads/:path*`
      },
      {
        source: '/generated_images/:path*',
        destination: `${apiBaseUrl}/generated_images/:path*`
      }
    ]
  }
}

module.exports = nextConfig
