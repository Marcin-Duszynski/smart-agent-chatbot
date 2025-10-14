# Design Document

## Overview

The embedded chatbot fails in cross-site contexts because cookies lack the required `SameSite=None; Secure` attributes. Modern browsers block cookies in iframes unless they have these attributes. The solution is to add middleware that modifies cookie headers to include the proper attributes for cross-site usage.

## Architecture

### Problem
- AWS Cognito and load balancer cookies don't have `SameSite=None; Secure` attributes
- Browser blocks these cookies when chatbot is embedded in iframe on different domain
- Authentication fails with "cross-site cookie" warnings

### Solution
Add FastAPI middleware that intercepts response cookies and adds the required attributes:
- `SameSite=None` for cross-site usage
- `Secure` for HTTPS environments
- Environment-aware configuration for development vs production

## Components and Interfaces

### Cookie Security Middleware

**File**: `chatbot-app/backend/middleware/cookie_security.py`

**Purpose**: Modify Set-Cookie headers to add `SameSite=None; Secure` attributes

**Key Methods**:
- `__call__()`: ASGI middleware entry point
- `_modify_cookie_header()`: Parse and modify cookie attributes
- `_is_https_request()`: Detect if request is over HTTPS

### Configuration Updates

**File**: `chatbot-app/backend/config.py`

**New Settings**:
- `ENABLE_CROSS_SITE_COOKIES`: Enable/disable cookie modification
- Auto-detect HTTPS vs HTTP for `Secure` attribute

## Data Models

### Cookie Modification Logic

The middleware will:
1. Parse existing Set-Cookie headers
2. Add `SameSite=None` if not present
3. Add `Secure` if HTTPS is detected
4. Preserve existing cookie attributes

## Error Handling

### HTTPS Detection
- Only add `Secure` attribute when request is over HTTPS
- Skip `Secure` in local development (HTTP)
- Log when cookies are modified for debugging

### Graceful Fallbacks
- If cookie parsing fails, pass through original cookie
- Preserve existing cookie attributes
- Don't break existing functionality

## Testing Strategy

### Manual Testing
- Test embedded chatbot in iframe on different domain
- Verify no browser cookie warnings appear
- Confirm authentication works in embedded context
- Check cookies have correct attributes in browser dev tools

### Environment Testing
- Local development: HTTP with `SameSite=None` (no `Secure`)
- Production: HTTPS with `SameSite=None; Secure`