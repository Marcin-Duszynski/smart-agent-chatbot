from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

class CookieSecurityMiddleware(BaseHTTPMiddleware):
    """Middleware to modify Set-Cookie headers for cross-site compatibility"""
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Skip if no cookies to modify
        if 'set-cookie' not in response.headers:
            return response
        
        # Detect HTTPS
        is_https = (request.url.scheme == 'https' or 
                   request.headers.get('x-forwarded-proto') == 'https')
        
        # Modify each Set-Cookie header
        cookie_headers = response.headers.getlist('set-cookie')
        response.headers.pop('set-cookie', None)
        
        for cookie_header in cookie_headers:
            modified_cookie = self._add_cross_site_attributes(cookie_header, is_https)
            response.headers.append('set-cookie', modified_cookie)
        
        return response
    
    def _add_cross_site_attributes(self, cookie_header: str, is_https: bool) -> str:
        """Add SameSite=None and Secure attributes if not present"""
        cookie_lower = cookie_header.lower()
        
        # Add SameSite=None if not present
        if 'samesite=' not in cookie_lower:
            cookie_header += '; SameSite=None'
        
        # Add Secure if HTTPS and not present
        if is_https and 'secure' not in cookie_lower:
            cookie_header += '; Secure'
        
        return cookie_header