# Implementation Plan

- [x] 1. Create cookie security middleware
  - Create middleware file to intercept and modify Set-Cookie headers
  - Implement ASGI middleware pattern for FastAPI
  - Add logic to parse existing cookie attributes and append cross-site attributes
  - _Requirements: 1.1, 1.2_

- [x] 1.1 Implement cookie header parsing and modification
  - Use simple string operations to modify Set-Cookie headers
  - Add logic to append `SameSite=None` attribute if not present
  - Add logic to append `Secure` attribute when HTTPS is detected
  - Preserve existing cookie attributes using minimal parsing
  - _Requirements: 1.1, 1.2_

- [x] 1.2 Add HTTPS detection logic
  - Implement simplified HTTPS detection using request scheme and x-forwarded-proto header
  - Only add `Secure` attribute when HTTPS is confirmed
  - _Requirements: 1.4_

- [x] 2. Integrate middleware into FastAPI application
  - Add cookie security middleware to the FastAPI app middleware stack
  - Ensure middleware runs after CORS but before other response processing
  - _Requirements: 1.1, 1.2, 1.3_

- [ ] 3. Test embedded chatbot functionality
  - Test chatbot embedding in cross-site iframe context
  - Verify authentication works without browser warnings
  - Confirm cookies have correct attributes in browser developer tools
  - Test both HTTP (development) and HTTPS (production) scenarios
  - _Requirements: 1.1, 1.2, 1.3, 1.4_

- [ ]* 4. Create test cases for cookie modification
  - Write unit tests for cookie header modification
  - Test HTTPS detection logic
  - Test middleware integration with FastAPI
  - _Requirements: 1.1, 1.2, 1.4_