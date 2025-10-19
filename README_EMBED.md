# Iframe Embedding Guide

This guide provides comprehensive instructions for embedding the AI chatbot into your website or application using iframes.

## 🚀 Quick Start

### Interactive Demo
Visit the live embedding examples at `/embed-example.html` (available when running the application) to see responsive embedding and pop-up chat widget in action.

### Basic Embedding

```html
<iframe 
  src="https://your-chatbot-domain.com/embed" 
  width="100%" 
  height="600"
  frameborder="0"
  title="AI Chatbot">
</iframe>
```

For local development, use `http://localhost:3000/embed`.

## 📋 Configuration Requirements

### 1. Domain Configuration
Before embedding, ensure your domain is configured in the deployment settings:

**Backend CORS Configuration:**
```bash
# In your .env file
CORS_ORIGINS=https://your-website.com,https://another-domain.com
```

**Frontend CORS Configuration:**
```bash
# In your frontend .env file  
CORS_ORIGINS=https://your-website.com,https://another-domain.com
```

### 2. Security Headers
If your parent page uses Content Security Policy (CSP), allow iframe embedding:

```http
Content-Security-Policy: frame-src 'self' https://your-chatbot-domain.com;
```

## 🎨 Embedding Examples

### Responsive Embedding
Perfect for most websites and applications:

```html
<!-- Responsive container -->
<div style="position: relative; width: 100%; height: 600px;">
  <iframe 
    src="https://your-chatbot-domain.com/embed"
    style="position: absolute; top: 0; left: 0; width: 100%; height: 100%;"
    frameborder="0"
    title="AI Chatbot">
  </iframe>
</div>
```

### Fixed Dimensions
For sidebar or specific layout requirements:

```html
<!-- Fixed size embedding -->
<iframe 
  src="https://your-chatbot-domain.com/embed"
  width="400" 
  height="700"
  style="border: 1px solid #e5e7eb; border-radius: 12px;"
  title="AI Chatbot">
</iframe>
```

### Floating Chat Widget
Create a pop-up chat experience (see `embed-example.html` for complete implementation):

```html
<!-- Floating widget structure -->
<div class="floating-widget">
  <div class="chatbot-icon" onclick="toggleWidget()">
    <img src="chatbot-icon.svg" alt="Chatbot" class="chatbot-icon-svg">
    <div class="tooltip">Ask AI Assistant</div>
  </div>
  <div class="widget-container" id="floatingWidget">
    <div class="widget-title-bar">
      <div class="widget-title">
        <img src="chatbot-icon-white.svg" alt="AI" class="widget-title-icon">
        AI Assistant
      </div>
      <button class="widget-close-btn" onclick="toggleWidget()">✕</button>
    </div>
    <div class="widget-iframe-container">
      <iframe src="https://your-chatbot-domain.com/embed"></iframe>
    </div>
  </div>
</div>
```

## 🔧 Framework Integration

### React Component
```jsx
const ChatbotEmbed = ({ width = "100%", height = "600px" }) => (
  <iframe 
    src="https://your-chatbot-domain.com/embed"
    width={width}
    height={height}
    style={{ border: 'none', borderRadius: '8px' }}
    title="AI Chatbot"
  />
);
```

### Vue Component
```vue
<template>
  <iframe 
    :src="chatbotUrl"
    :width="width"
    :height="height"
    frameborder="0"
    title="AI Chatbot"
    class="chatbot-iframe">
  </iframe>
</template>

<script>
export default {
  props: {
    width: { type: String, default: '100%' },
    height: { type: String, default: '600px' }
  },
  data() {
    return {
      chatbotUrl: 'https://your-chatbot-domain.com/embed'
    }
  }
}
</script>
```

### Angular Component
```typescript
// chatbot-embed.component.ts
import { Component, Input } from '@angular/core';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';

@Component({
  selector: 'app-chatbot-embed',
  template: `
    <iframe 
      [src]="trustedUrl"
      [width]="width"
      [height]="height"
      frameborder="0"
      title="AI Chatbot">
    </iframe>
  `
})
export class ChatbotEmbedComponent {
  @Input() width = '100%';
  @Input() height = '600px';
  
  trustedUrl: SafeResourceUrl;
  
  constructor(private sanitizer: DomSanitizer) {
    this.trustedUrl = this.sanitizer.bypassSecurityTrustResourceUrl(
      'https://your-chatbot-domain.com/embed'
    );
  }
}
```

## 📡 Cross-Origin Communication

### Authentication Status
Listen for authentication events from the embedded chatbot:

```javascript
window.addEventListener('message', function(event) {
  // Verify origin for security
  if (event.origin !== 'https://your-chatbot-domain.com') return;
  
  if (event.data?.type === 'CHATBOT_AUTH_STATUS') {
    const { isAuthenticated, userId } = event.data.payload;
    console.log('Authentication status:', isAuthenticated);
    
    // Handle authentication state in your app
    if (isAuthenticated) {
      showWelcomeMessage(userId);
    }
  }
});
```

### Send Configuration to Chatbot
```javascript
// Send theme or configuration to the embedded chatbot
const iframe = document.getElementById('chatbot-iframe');
iframe.contentWindow.postMessage({
  type: 'CONFIG_UPDATE',
  payload: {
    theme: 'dark',
    language: 'en'
  }
}, 'https://your-chatbot-domain.com');
```

## 🎯 Use Case Examples

### Customer Support Portal
```html
<!DOCTYPE html>
<html>
<head>
  <title>Support Portal</title>
  <style>
    .support-layout {
      display: grid;
      grid-template-columns: 1fr 400px;
      gap: 20px;
      height: 100vh;
    }
    .chatbot-panel {
      border-left: 1px solid #e5e7eb;
      background: #f9fafb;
    }
  </style>
</head>
<body>
  <div class="support-layout">
    <main>
      <!-- Your support content -->
      <h1>Help Center</h1>
    </main>
    <aside class="chatbot-panel">
      <iframe 
        src="https://your-chatbot-domain.com/embed"
        width="100%" 
        height="100%"
        frameborder="0"
        title="AI Support Assistant">
      </iframe>
    </aside>
  </div>
</body>
</html>
```

### Dashboard Integration
```html
<!-- Embedded in admin dashboard -->
<div class="dashboard-grid">
  <div class="dashboard-card">
    <div class="card-header">
      <h3>AI Assistant</h3>
      <button onclick="reloadChatbot()">Refresh</button>
    </div>
    <div class="card-content">
      <iframe 
        id="dashboard-chatbot"
        src="https://your-chatbot-domain.com/embed"
        width="100%" 
        height="500"
        style="border: none; background: white; border-radius: 8px;"
        title="Dashboard AI Assistant">
      </iframe>
    </div>
  </div>
</div>
```

## 🔍 Troubleshooting

### Common Issues

**❌ Iframe not loading**
- Verify the chatbot URL is accessible
- Check CORS configuration includes your domain
- Ensure SSL certificates are valid for HTTPS

**❌ Authentication not working**
- Confirm domain is added to allowed origins
- Check browser console for CORS errors
- Verify postMessage event listeners are set up correctly

**❌ Responsive issues**
- Use percentage-based dimensions for responsive behavior
- Test across different screen sizes and devices
- Consider CSS media queries for adaptive sizing

**❌ Security errors**
- Update Content Security Policy headers
- Ensure iframe src uses HTTPS in production
- Verify domain configuration in deployment settings

### Debug Mode
Enable debug logging by adding URL parameters:

```html
<iframe src="https://your-chatbot-domain.com/embed?debug=true"></iframe>
```

### Testing Authentication
Use the interactive demo at `/embed-example.html` to test authentication status and iframe functionality before implementing in your application.

## 📚 Complete Example

For a fully working example with CSS, JavaScript, and responsive design, see:
- **Interactive Demo**: `/embed-example.html` (when running the application)
- **Source Files**: 
  - `chatbot-app/frontend/public/embed-example.html`
  - `chatbot-app/frontend/public/embed-example.css`
  - `chatbot-app/frontend/public/embed-example.js`

## 🚀 Production Deployment

### Environment Configuration
1. **Update CORS origins** in both backend and frontend `.env` files
2. **Configure SSL certificates** for HTTPS
3. **Test embedding** from your production domain
4. **Monitor authentication** and error logs

### Performance Optimization
- Use `loading="lazy"` attribute for off-screen iframes
- Implement loading states for better user experience
- Consider iframe preloading for frequently accessed pages

### Security Best Practices
- Always use HTTPS in production
- Implement proper CSP headers
- Validate postMessage origins
- Regular security audits of embedded content

---

For additional support and advanced configuration options, refer to the main [README.md](README.md) file.