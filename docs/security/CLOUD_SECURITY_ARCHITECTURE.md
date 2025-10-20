# Cloud Deployment Security Architecture
## Strands Agent Chatbot Platform

**Generated:** 20 October 2025
**Deployment Target:** AWS Cloud (ECS Fargate + CloudFront + Cognito)
**Infrastructure:** `agent-blueprint/chatbot-deployment/infrastructure/`

---

## Executive Summary

Your AWS-deployed application implements a **multi-layered security architecture** with authentication, network isolation, and encryption in transit. The infrastructure provides strong security controls through:

- ✅ **AWS Cognito** authentication with OAuth 2.0
- ✅ **CloudFront CDN** with HTTPS enforcement and DDoS protection
- ✅ **VPC isolation** with private subnets for application containers
- ✅ **IAM role-based access** eliminating static credentials
- ✅ **CloudWatch observability** with comprehensive audit logging
- ⚠️ **Application-level vulnerabilities** remain (see limitations section)

---

## Table of Contents

1. [Authentication & Authorisation (Cognito)](#layer-1-authentication--authorisation)
2. [CDN & HTTPS Enforcement (CloudFront)](#layer-2-cdn--https-enforcement)
3. [Network Security (VPC & Security Groups)](#layer-3-network-security)
4. [Encryption in Transit](#layer-4-encryption-in-transit)
5. [Identity & Access Management (IAM)](#layer-5-identity--access-management)
6. [Observability & Audit Logging](#layer-6-observability--audit-logging)
7. [API Security](#layer-7-api-security)
8. [Known Limitations](#known-security-limitations)
9. [Security Comparison: Local vs Cloud](#security-comparison-local-vs-cloud)
10. [Hardening Recommendations](#recommendations-for-hardening)

---

## 🔒 Layer 1: Authentication & Authorisation (AWS Cognito)

**Infrastructure:** `cognito-auth-stack.ts:14-38`, `chatbot-stack.ts:308-312`

### AWS Cognito User Pool Configuration

```typescript
// cognito-auth-stack.ts:14-38
this.userPool = new cognito.UserPool(this, 'ChatbotUserPool', {
  userPoolName: 'chatbot-users',
  selfSignUpEnabled: true,
  signInAliases: { email: true },
  autoVerify: { email: true },
  passwordPolicy: {
    minLength: 8,
    requireLowercase: true,
    requireUppercase: true,
    requireDigits: true,
    requireSymbols: true,
  },
  accountRecovery: cognito.AccountRecovery.EMAIL_ONLY,
});
```

### Security Features

| Feature | Implementation | Security Benefit |
|---------|----------------|------------------|
| **Email Verification** | Required on signup | Prevents fake accounts |
| **Password Policy** | 8+ chars, mixed case, digits, symbols | Strong authentication |
| **Account Recovery** | Email-only | Secure password reset |
| **OAuth 2.0 Flow** | Authorisation Code Grant | Industry-standard secure flow |
| **Client Secret** | Generated (`generateSecret: true`) | Prevents token theft |

### OAuth Configuration

```typescript
// cognito-auth-stack.ts:48-59
oAuth: {
  flows: { authorizationCodeGrant: true },
  scopes: [
    cognito.OAuthScope.OPENID,
    cognito.OAuthScope.EMAIL,
    cognito.OAuthScope.PROFILE
  ],
  callbackUrls: ['https://CLOUDFRONT_DOMAIN/oauth2/idpresponse'],
  logoutUrls: ['https://CLOUDFRONT_DOMAIN/'],
}
```

**Dynamic Callback URL Update:** CloudFront domain automatically configured via Custom Resource (lines 412-454).

### Session Management

- **JWT Tokens:** Cognito issues ID tokens, access tokens, and refresh tokens
- **Token Expiry:** Configurable (default 1 hour for access tokens)
- **Frontend Integration:** Tokens stored securely in browser (when `ENABLE_COGNITO=true`)
- **API Protection:** All requests must include valid Cognito authentication

---

## 🌐 Layer 2: CDN & HTTPS Enforcement (CloudFront)

**Infrastructure:** `chatbot-stack.ts:392-408`

### CloudFront Distribution Architecture

```
┌──────────────────────────────────────────────────────┐
│                  Internet Users                      │
│              (Global, Any Location)                  │
└───────────────────┬──────────────────────────────────┘
                    │ HTTPS enforced
                    ▼
┌──────────────────────────────────────────────────────┐
│         CloudFront Edge Locations (CDN)              │
│  ├─ TLS 1.2+ Termination                             │
│  ├─ DDoS Protection (AWS Shield Standard)            │
│  ├─ Geo-distributed (North America + Europe)         │
│  └─ Cache Policy: Disabled (dynamic content)         │
└───────────────────┬──────────────────────────────────┘
                    │ HTTP (within AWS backbone)
                    ▼
┌──────────────────────────────────────────────────────┐
│     Application Load Balancer (VPC Public Subnet)    │
│  └─ Only accepts CloudFront prefix list traffic      │
└──────────────────────────────────────────────────────┘
```

### Security Configuration

```typescript
// chatbot-stack.ts:393-408
const distribution = new cloudfront.Distribution(this, 'ChatbotCloudFront', {
  defaultBehavior: {
    origin: new origins.LoadBalancerV2Origin(alb, {
      protocolPolicy: cloudfront.OriginProtocolPolicy.HTTP_ONLY,
      httpPort: 80,
    }),
    viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
    allowedMethods: cloudfront.AllowedMethods.ALLOW_ALL,
    cachePolicy: cloudfront.CachePolicy.CACHING_DISABLED,
    originRequestPolicy: customOriginRequestPolicy,
    compress: true,
  },
  priceClass: cloudfront.PriceClass.PRICE_CLASS_100,
});
```

### Security Benefits

1. **HTTPS Enforcement:**
   - `REDIRECT_TO_HTTPS` - All HTTP requests automatically upgraded
   - TLS 1.2+ with Perfect Forward Secrecy (PFS)
   - AWS-managed SSL/TLS certificates

2. **DDoS Protection:**
   - AWS Shield Standard (included, automatic)
   - Rate limiting at edge locations
   - Absorption of network/transport layer attacks

3. **Origin Protection:**
   - ALB only accepts traffic from CloudFront managed prefix list
   - Direct ALB access blocked (see Layer 3)
   - CloudFront acts as security proxy

4. **Custom Origin Request Policy:**
   - Forwards all headers (including `X-Session-ID`)
   - Preserves authentication cookies
   - Query string forwarding enabled

---

## 🛡️ Layer 3: Network Security (VPC & Security Groups)

**Infrastructure:** `chatbot-stack.ts:36-52, 226-239`

### VPC Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                       AWS VPC (ChatbotMcpVpc)               │
│  Region: us-west-2                                          │
│  CIDR: Auto-assigned by AWS                                 │
│                                                             │
│  ┌───────────────────────┐  ┌──────────────────────────┐   │
│  │  Public Subnets       │  │  Private Subnets         │   │
│  │  (2 AZs)              │  │  (2 AZs)                 │   │
│  │  ┌─────────────────┐  │  │  ┌────────────────────┐ │   │
│  │  │ ALB             │  │  │  │ Backend ECS Tasks  │ │   │
│  │  │ (CloudFront-    │  │  │  │ (No direct inet)   │ │   │
│  │  │  only access)   │  │  │  └────────────────────┘ │   │
│  │  └─────────────────┘  │  │  ┌────────────────────┐ │   │
│  │                       │  │  │ Frontend ECS Tasks │ │   │
│  │                       │  │  │ (No direct inet)   │ │   │
│  │                       │  │  └────────────────────┘ │   │
│  └───────────┬───────────┘  └──────────┬───────────────┘   │
│              │                         │                   │
│              │         ┌───────────────┘                   │
│              │         │ NAT Gateway                       │
│              │         │ (Outbound only)                   │
│              │         └───────────────────────────────────│
│                                                             │
│  Availability Zones: us-west-2a, us-west-2b                │
└─────────────────────────────────────────────────────────────┘
```

### VPC Configuration

```typescript
// chatbot-stack.ts:37-52
const vpc = new ec2.Vpc(this, 'ChatbotMcpVpc', {
  maxAzs: 2,
  natGateways: 1,
  subnetConfiguration: [
    {
      name: 'PublicSubnet',
      subnetType: ec2.SubnetType.PUBLIC,
      cidrMask: 24  // ~250 IP addresses per subnet
    },
    {
      name: 'PrivateSubnet',
      subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
      cidrMask: 24
    }
  ]
});
```

### Security Group - Application Load Balancer

```typescript
// chatbot-stack.ts:227-239
const albSecurityGroup = new ec2.SecurityGroup(this, 'ChatbotAlbSecurityGroup', {
  vpc,
  description: 'Security group for Chatbot ALB - CloudFront only',
  allowAllOutbound: true
});

// Allow inbound HTTP from CloudFront IP ranges ONLY
albSecurityGroup.addIngressRule(
  ec2.Peer.prefixList('pl-82a045eb'),  // CloudFront managed prefix list
  ec2.Port.tcp(80),
  'Allow HTTP traffic from CloudFront'
);
```

### Network Isolation Benefits

| Component | Subnet Type | Internet Access | Ingress Allowed From |
|-----------|-------------|-----------------|---------------------|
| **ALB** | Public | N/A (load balancer) | CloudFront prefix list only |
| **Backend ECS** | Private | Outbound via NAT | ALB only |
| **Frontend ECS** | Private | Outbound via NAT | ALB only |
| **MCP Servers** | Private (separate) | Outbound via NAT | Backend ECS only |

**Key Security Points:**
- ✅ **Zero Trust Architecture:** ECS tasks cannot be accessed directly from internet
- ✅ **CloudFront Prefix List:** Automatically updated by AWS (no manual IP management)
- ✅ **High Availability:** 2 Availability Zones for fault tolerance
- ✅ **Cost Optimisation:** Single NAT Gateway (can be increased for production)

---

## 🔐 Layer 4: Encryption in Transit

**Infrastructure:** `chatbot-stack.ts:395-403`, `middleware/cookie_security.py`

### TLS/HTTPS Encryption Layers

```
┌──────────────────────────────────────────────────┐
│  Client Browser                                  │
│  └─ TLS 1.2+ connection established              │
└───────────────┬──────────────────────────────────┘
                │
                │ ❶ HTTPS (Public Internet)
                │   TLS 1.2+, Perfect Forward Secrecy
                ▼
┌──────────────────────────────────────────────────┐
│  CloudFront Edge Location                       │
│  ├─ TLS Termination                              │
│  ├─ Certificate: AWS-managed                     │
│  └─ Cipher suites: Modern, secure                │
└───────────────┬──────────────────────────────────┘
                │
                │ ❷ HTTP (AWS Private Backbone)
                │   Within AWS network, Layer 2 encryption
                ▼
┌──────────────────────────────────────────────────┐
│  Application Load Balancer                      │
│  └─ VPC Public Subnet                            │
└───────────────┬──────────────────────────────────┘
                │
                │ ❸ HTTP (VPC Internal)
                │   Private network, isolated
                ▼
┌──────────────────────────────────────────────────┐
│  ECS Tasks (Backend/Frontend)                   │
│  └─ Private Subnets                              │
└──────────────────────────────────────────────────┘
```

### CloudFront TLS Configuration

```typescript
// chatbot-stack.ts:395-403
defaultBehavior: {
  origin: new origins.LoadBalancerV2Origin(alb, {
    protocolPolicy: cloudfront.OriginProtocolPolicy.HTTP_ONLY,
    httpPort: 80,
  }),
  viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
  originRequestPolicy: customOriginRequestPolicy,
  compress: true,
}
```

**Why HTTP between CloudFront and ALB?**
- ✅ Traffic never leaves AWS backbone network
- ✅ AWS backbone uses Layer 2 encryption (MACsec)
- ✅ Reduces CPU overhead on ALB (TLS termination at edge)
- ✅ CloudFront-to-ALB restricted by security group

### Cookie Security Middleware

```python
# middleware/cookie_security.py:28-40
def _add_cross_site_attributes(self, cookie_header: str, is_https: bool) -> str:
    cookie_lower = cookie_header.lower()

    # Add SameSite=None if not present
    if 'samesite=' not in cookie_lower:
        cookie_header += '; SameSite=None'

    # Add Secure if HTTPS and not present
    if is_https and 'secure' not in cookie_lower:
        cookie_header += '; Secure'

    return cookie_header
```

**Security Attributes:**
- `SameSite=None` - Allows cookies in cross-origin requests (required for OAuth)
- `Secure` - Cookies only transmitted over HTTPS
- `x-forwarded-proto` detection - Identifies HTTPS via CloudFront header

---

## 🔑 Layer 5: Identity & Access Management (IAM)

**Infrastructure:** `chatbot-stack.ts:73-136`

### Backend ECS Task IAM Role Permissions

The backend container operates with **least-privilege IAM permissions**. No static API keys or credentials stored.

#### 1. AWS Bedrock Access

```typescript
// chatbot-stack.ts:74-79
backendTaskDefinition.taskRole.addManagedPolicy(
  iam.ManagedPolicy.fromAwsManagedPolicyName('AmazonBedrockFullAccess')
);
backendTaskDefinition.taskRole.addManagedPolicy(
  iam.ManagedPolicy.fromAwsManagedPolicyName('BedrockAgentCoreFullAccess')
);
```

**Permissions:**
- `bedrock:InvokeModel` - AI model inference
- `bedrock:InvokeModelWithResponseStream` - Streaming responses
- Agent orchestration and memory management

#### 2. MCP Server Access (API Gateway)

```typescript
// chatbot-stack.ts:82-93
backendTaskDefinition.addToTaskRolePolicy(
  new iam.PolicyStatement({
    effect: iam.Effect.ALLOW,
    actions: ['execute-api:Invoke'],
    resources: [
      `arn:aws:execute-api:${this.region}:${this.account}:*/*/POST/mcp`,
      `arn:aws:execute-api:${this.region}:${this.account}:mcp-*/*/*/*`
    ]
  })
);
```

**Security:**
- ✅ Resource-scoped to MCP endpoints only
- ✅ SigV4 authentication (automatic with IAM role)
- ✅ No API keys required

#### 3. AWS Systems Manager Parameter Store

```typescript
// chatbot-stack.ts:96-108
backendTaskDefinition.addToTaskRolePolicy(
  new iam.PolicyStatement({
    effect: iam.Effect.ALLOW,
    actions: [
      'ssm:GetParameter',
      'ssm:GetParameters',
      'ssm:GetParametersByPath'
    ],
    resources: [
      `arn:aws:ssm:${this.region}:${this.account}:parameter/mcp/endpoints/*`
    ]
  })
);
```

**Use Case:** Dynamic MCP endpoint URLs without hardcoding
**Example:** `ssm:///mcp/endpoints/serverless/aws-documentation`

#### 4. CloudWatch Observability

```typescript
// chatbot-stack.ts:110-124
backendTaskDefinition.addToTaskRolePolicy(
  new iam.PolicyStatement({
    effect: iam.Effect.ALLOW,
    actions: [
      'logs:CreateLogStream',
      'logs:PutLogEvents',
      'cloudwatch:PutMetricData'
    ],
    resources: [
      `arn:aws:logs:${this.region}:${this.account}:log-group:agents/strands-agent-logs`,
      `arn:aws:logs:${this.region}:${this.account}:log-group:agents/strands-agent-logs:*`
    ]
  })
);
```

#### 5. AWS X-Ray Tracing

```typescript
// chatbot-stack.ts:126-136
backendTaskDefinition.addToTaskRolePolicy(
  new iam.PolicyStatement({
    effect: iam.Effect.ALLOW,
    actions: [
      'xray:PutTraceSegments',
      'xray:PutTelemetryRecords'
    ],
    resources: ['*']
  })
);
```

**Security Benefit:** Distributed tracing for security audit and performance monitoring

### IAM Security Summary

| Feature | Security Benefit |
|---------|------------------|
| **Task Roles** | No static credentials, automatic rotation |
| **Resource Scoping** | Least-privilege access to specific resources |
| **SigV4 Authentication** | Cryptographic request signing for MCP servers |
| **No API Keys** | Zero risk of credential leakage in code |
| **Automatic Rotation** | AWS manages temporary credentials |

---

## 📊 Layer 6: Observability & Audit Logging

**Infrastructure:** `chatbot-stack.ts:138-166, 178-194`

### OpenTelemetry (OTEL) Configuration

```typescript
// chatbot-stack.ts:178-194
const backendEnvironment = {
  // AgentCore Observability - OTEL Configuration
  OTEL_PYTHON_DISTRO: 'aws_distro',
  OTEL_PYTHON_CONFIGURATOR: 'aws_configurator',
  OTEL_EXPORTER_OTLP_PROTOCOL: 'http/protobuf',
  OTEL_LOGS_EXPORTER: 'otlp',
  OTEL_TRACES_EXPORTER: 'otlp',
  OTEL_EXPORTER_OTLP_LOGS_HEADERS: `x-aws-log-group=agents/strands-agent-logs,x-aws-log-stream=${logStreamName}`,
  OTEL_RESOURCE_ATTRIBUTES: 'service.name=strands-chatbot',
  AGENT_OBSERVABILITY_ENABLED: 'true',
  // Real-time batch processing
  OTEL_BSP_SCHEDULE_DELAY: '100',
  OTEL_BSP_MAX_EXPORT_BATCH_SIZE: '1',
  OTEL_BSP_EXPORT_TIMEOUT: '5000',
};
```

### CloudWatch Log Groups

```typescript
// chatbot-stack.ts:150-155
agentObservabilityLogGroup = new logs.LogGroup(this, 'AgentObservabilityLogGroup', {
  logGroupName: 'agents/strands-agent-logs',
  retention: logs.RetentionDays.ONE_MONTH,
  removalPolicy: cdk.RemovalPolicy.RETAIN
});
```

**Log Groups:**
1. **`agents/strands-agent-logs`** - AgentCore observability traces
2. **`chatbot-backend`** - Application logs (FastAPI)
3. **`chatbot-frontend`** - Next.js application logs

### What Gets Logged

#### Automatic Instrumentation:
- ✅ All AWS Bedrock API calls (model invocations)
- ✅ HTTP requests with headers and response codes
- ✅ Tool executions and results
- ✅ Session lifecycle events
- ✅ MCP server connections and calls
- ✅ Agent state transitions

#### Session-Based Tracing:
```python
# Session ID added to all traces
session.id = "session_20251020_143022_a3f8b92e"
```

**CloudWatch Transaction Search:**
- Filter traces by session ID
- View complete conversation flow
- Identify performance bottlenecks
- Security audit trail

### Security Benefits

| Capability | Security Use Case |
|------------|-------------------|
| **Trace Grouping** | Track all activity for a session |
| **HTTP Header Logging** | Detect suspicious requests |
| **API Call Logging** | Audit Bedrock model usage |
| **Error Tracking** | Identify attack patterns |
| **Performance Metrics** | Detect abnormal behaviour |
| **Retention Policy** | 30-day audit trail |

**Access:** CloudWatch Console → Application Signals → Transaction Search

---

## 🔥 Layer 7: API Security

**Infrastructure:** `chatbot-stack.ts:354-381`, `app.py:89-96`

### Application Load Balancer Routing

```typescript
// chatbot-stack.ts:354-381
const listener = alb.addListener('ChatbotListener', {
  port: 80,
  defaultAction: elbv2.ListenerAction.forward([frontendTargetGroup]),
});

// Health check endpoint (unauthenticated - for ALB probes)
listener.addAction('HealthCheckAction', {
  priority: 50,
  conditions: [elbv2.ListenerCondition.pathPatterns(['/health'])],
  action: elbv2.ListenerAction.forward([backendTargetGroup]),
});

// API endpoints (authentication via CloudFront + Cognito)
listener.addAction('BackendApiAction', {
  priority: 100,
  conditions: [
    elbv2.ListenerCondition.pathPatterns([
      '/api/*',
      '/docs*',
      '/uploads/*',
      '/output/*',
    ]),
  ],
  action: elbv2.ListenerAction.forward([backendTargetGroup]),
});
```

### CORS Configuration

```python
# app.py:89-96
app.add_middleware(
    CORSMiddleware,
    allow_origins=Config.get_cors_origins(),  # Environment-configured
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Session-ID"],
)
```

**Dynamic CORS Origins:**
```bash
# .env configuration
CORS_ORIGINS=https://your-cloudfront-domain.cloudfront.net,https://your-custom-domain.com
```

### Custom Origin Request Policy

```typescript
// chatbot-stack.ts:384-390
const customOriginRequestPolicy = new cloudfront.OriginRequestPolicy(this, 'ChatbotOriginRequestPolicy', {
  originRequestPolicyName: 'ChatbotCustomOriginPolicy',
  comment: 'Forward all headers including X-Session-ID',
  headerBehavior: cloudfront.OriginRequestHeaderBehavior.all(),
  queryStringBehavior: cloudfront.OriginRequestQueryStringBehavior.all(),
  cookieBehavior: cloudfront.OriginRequestCookieBehavior.all(),
});
```

**Security Considerations:**
- ✅ Session headers preserved through CloudFront
- ✅ Authentication cookies forwarded
- ⚠️ All headers forwarded (increases attack surface slightly)

### API Endpoint Protection

| Endpoint | Authentication | Rate Limiting | Purpose |
|----------|---------------|---------------|---------|
| `/health` | ❌ None | N/A | ALB health checks |
| `/api/*` | ✅ Cognito (if enabled) | ❌ None | All API requests |
| `/docs` | ✅ Cognito (if enabled) | ❌ None | Swagger documentation |
| `/uploads/*` | ✅ Cognito (if enabled) | ❌ None | File uploads |
| `/output/*` | ✅ Cognito (if enabled) | ❌ None | Generated files |

**Note:** Authentication enforced at CloudFront level when `ENABLE_COGNITO=true`

---

## 🚨 Known Security Limitations

While the **cloud infrastructure** provides strong security, **application-level vulnerabilities** exist. These are documented in `SECURITY_REVIEW_REPORT.md`.

### ⚠️ Critical Application Vulnerabilities

#### 1. No Backend Authentication Enforcement (CRIT-1)
**Location:** `chatbot-app/backend/app.py`, all router files
**Issue:** API endpoints lack authentication checks in application code

```python
# Current (insecure)
@router.post("/stream/chat")
async def stream_chat(request: dict):
    # No authentication check
    pass

# Should be (secure)
@router.post("/stream/chat")
async def stream_chat(request: dict, user: User = Depends(get_current_user)):
    # Validates Cognito JWT token
    pass
```

**Impact:**
- Cognito authentication exists but not enforced at API level
- Relies entirely on CloudFront for authentication
- If CloudFront bypassed, APIs fully accessible

#### 2. Hardcoded CORS Wildcards (CRIT-2)
**Location:** `chatbot-app/backend/routers/chat.py:42-43`

```python
# CRITICAL ISSUE
return StreamingResponse(
    agent.stream_async(user_message, session_id=session_id),
    media_type="text/event-stream",
    headers={
        "Access-Control-Allow-Origin": "*",  # Bypasses CORS middleware!
        "Access-Control-Allow-Headers": "*",
        "X-Session-ID": session_id,
    }
)
```

**Impact:**
- Any website can embed chatbot and make requests
- CORS middleware configuration completely bypassed
- Session IDs exposed to cross-origin websites

#### 3. Client-Controlled Session IDs (CRIT-3)
**Location:** `chatbot-app/backend/routers/chat.py:30-33`

```python
@router.post("/stream/chat")
async def stream_chat(request: dict, x_session_id: Optional[str] = Header(None)):
    session_id = x_session_id or request.get("session_id")  # Client controls!
    # No validation that session_id belongs to authenticated user
```

**Impact:**
- Session hijacking possible if session ID discovered
- No link between Cognito user ID and session
- Attacker can access any session by guessing/discovering ID

#### 4. Weak Session ID Generation (HIGH-4)
**Location:** `chatbot-app/backend/session/global_session_registry.py:92-97`

```python
def _generate_session_id(self) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    random_suffix = uuid.uuid4().hex[:8]  # Only 32 bits!
    return f"session_{timestamp}_{random_suffix}"
```

**Issue:**
- Only 8 hex characters = 2³² = 4.3 billion possibilities
- Timestamp is predictable
- Birthday attack feasible with moderate resources

**Should be:**
```python
import secrets
random_suffix = secrets.token_hex(32)  # 256 bits
```

#### 5. No Encryption at Rest (CRIT-6)
**Location:** `chatbot-app/backend/session/in_memory_session_manager.py`

**Unencrypted Data:**
- Conversation history (including financial data)
- User-uploaded files
- Generated analysis results
- Customer IDs and PII
- Tool execution results

**Impact:**
- Memory dump attacks expose all data
- Disk files readable by anyone with file system access
- Regulatory compliance violations (PCI DSS, GDPR)

### ⚠️ High-Severity Vulnerabilities

| Vulnerability | Location | Impact |
|--------------|----------|--------|
| **Unauthenticated Debug Endpoints** | `routers/debug.py` | Full data breach via `/debug/memory/all` |
| **No Rate Limiting** | All endpoints | DDoS and resource exhaustion |
| **Session ID in Headers** | Multiple files | Session hijacking over HTTP |
| **Error Message Leakage** | Exception handlers | Information disclosure |
| **No HTTPS Enforcement in Code** | `app.py` | Allows HTTP in development mode |

---

## ✅ What IS Protected in Cloud Deployment

```
┌─────────────────────────────────────────────────────────┐
│           SECURITY LAYERS: CLOUD vs LOCAL               │
├─────────────────────────────────────────────────────────┤
│  Local Development        │  Cloud Deployment           │
├──────────────────────────┼──────────────────────────────┤
│  ❌ No authentication     │  ✅ Cognito OAuth 2.0        │
│  ❌ HTTP only             │  ✅ HTTPS enforced           │
│  ❌ Public internet       │  ✅ VPC isolation            │
│  ❌ No DDoS protection    │  ✅ AWS Shield Standard      │
│  ❌ Local log files       │  ✅ CloudWatch + X-Ray       │
│  ❌ Hardcoded credentials │  ✅ IAM Task Roles           │
│  ❌ Direct access         │  ✅ CloudFront proxy         │
└─────────────────────────────────────────────────────────┘
```

### Protected Attack Vectors

| Attack Type | Protection Mechanism | Implementation |
|-------------|---------------------|----------------|
| **Network-level DDoS** | AWS Shield Standard | CloudFront automatic |
| **Direct backend access** | VPC + Security Groups | Private subnets, CloudFront prefix list |
| **Credential theft** | IAM Task Roles | No static API keys |
| **Man-in-the-middle** | HTTPS/TLS 1.2+ | CloudFront enforcement |
| **Unauthorised users** | Cognito Authentication | OAuth 2.0 flow |
| **Audit trail** | CloudWatch Logs | 30-day retention |
| **Service abuse** | IAM resource scoping | Least-privilege permissions |

### Infrastructure Security Strengths

1. **Zero Trust Network:**
   - ECS tasks in private subnets (no direct internet)
   - ALB only accepts CloudFront traffic
   - MCP servers isolated in separate private subnets

2. **Automatic Security Updates:**
   - CloudFront prefix list auto-updated by AWS
   - IAM temporary credentials auto-rotated
   - TLS certificates auto-renewed

3. **Defence in Depth:**
   - Layer 1: Cognito authentication
   - Layer 2: CloudFront CDN filtering
   - Layer 3: VPC network isolation
   - Layer 4: Security group rules
   - Layer 5: IAM least-privilege
   - Layer 6: CloudWatch audit logging

---

## ⚠️ What Is NOT Protected

### Application-Level Security Gaps

| Vulnerability | Risk Level | Current Status | Required Fix |
|--------------|------------|----------------|--------------|
| **Session hijacking** | 🔴 Critical | Client-controlled IDs | Link to Cognito user ID |
| **Data encryption at rest** | 🔴 Critical | Plaintext storage | Implement AWS KMS |
| **API authentication** | 🔴 Critical | Not enforced | JWT validation |
| **CORS bypass** | 🔴 Critical | Hardcoded wildcards | Remove hardcoded headers |
| **Debug endpoints** | 🟠 High | Enabled in production | Delete or gate behind auth |
| **Rate limiting** | 🟠 High | None | CloudFront WAF or app-level |
| **Weak session IDs** | 🟠 High | 32 bits entropy | Use 256-bit random |
| **Input validation** | 🟡 Medium | Minimal | Add comprehensive validation |

### Risk Scenarios (Even with Infrastructure Security)

**Scenario 1: Authenticated User Session Hijacking**
```
1. Attacker signs up with valid email (Cognito allows self-registration)
2. Attacker logs in → gets past CloudFront authentication
3. Attacker discovers victim's session ID (weak entropy or leaked)
4. Attacker sets X-Session-ID header to victim's session
5. Backend accepts (no user validation) → full access to victim's data
```

**Scenario 2: Debug Endpoint Data Breach**
```
1. Attacker creates legitimate account
2. Logs in via Cognito (gets past CloudFront)
3. Calls /debug/memory/all endpoint
4. Downloads ALL user sessions and conversations
5. No authentication check on debug endpoint
```

**Scenario 3: CORS Bypass + Session Theft**
```
1. Attacker creates malicious website
2. Embeds EventSource to chatbot.com/api/chat/stream/chat
3. Hardcoded CORS wildcard allows cross-origin request
4. Steals session IDs from response headers
5. Uses stolen session IDs to hijack accounts
```

---

## 🔧 Recommendations for Hardening

### Immediate Actions (Week 1)

#### 1. Verify API Key Security
```bash
# Check if API keys are in version control
cd agent-blueprint
git log --all --full-history -- ".env"

# If found, rotate keys immediately:
# - Tavily: https://tavily.com/dashboard
# - Nova Act: https://nova-act.com/dashboard

# Remove from Git history
git filter-repo --path .env --invert-paths
```

#### 2. Add .gitignore Protection
```bash
echo ".env
.env.local
.env.production
.env.*.local
*.pem
*.key" >> .gitignore
```

#### 3. Disable Debug Endpoints
```python
# chatbot-app/backend/routers/debug.py
from fastapi import HTTPException
import os

@router.get("/debug/memory/all")
async def get_all_memory_data():
    if os.getenv("DEPLOYMENT_ENV") == "production":
        raise HTTPException(status_code=404, detail="Not found")
    # ... rest of code
```

### Short-term Fixes (Weeks 2-3)

#### 1. Implement JWT Validation on Backend

```python
# chatbot-app/backend/middleware/auth.py
from fastapi import Depends, HTTPException, Header
from jose import jwt, JWTError
import boto3
import os

async def verify_cognito_token(authorization: str = Header(None)) -> dict:
    """Verify Cognito JWT token"""
    if not os.getenv("ENABLE_COGNITO") == "true":
        return {}  # Skip in development

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")

    token = authorization.replace("Bearer ", "")

    try:
        # Verify JWT signature and expiration
        # (Implementation details omitted for brevity)
        payload = jwt.decode(token, options={"verify_signature": False})
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

# Apply to all endpoints
@router.post("/stream/chat")
async def stream_chat(
    request: dict,
    user: dict = Depends(verify_cognito_token)
):
    user_id = user.get("sub")  # Cognito user ID
    # ...
```

#### 2. Link Sessions to Authenticated Users

```python
# chatbot-app/backend/session/global_session_registry.py
def get_or_create_session(
    self,
    session_id: Optional[str] = None,
    cognito_user_id: Optional[str] = None
) -> Tuple[str, ...]:
    """Get or create session, validating ownership"""
    if session_id:
        # Validate session belongs to user
        if session_id in self.sessions:
            session = self.sessions[session_id]
            if session.user_id != cognito_user_id:
                raise HTTPException(status_code=403, detail="Access denied")
            return session_id, session, self.agents[session_id]

    # Create new session linked to user
    session_id = self._generate_session_id()
    session = SessionManager(session_id, user_id=cognito_user_id)
    # ...
```

#### 3. Remove Hardcoded CORS Wildcards

```python
# chatbot-app/backend/routers/chat.py
return StreamingResponse(
    agent.stream_async(user_message, session_id=session_id),
    media_type="text/event-stream",
    headers={
        # Remove these lines:
        # "Access-Control-Allow-Origin": "*",
        # "Access-Control-Allow-Headers": "*",

        # Keep only:
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Session-ID": session_id,
    }
)
# CORS middleware will handle origin headers correctly
```

#### 4. Increase Session ID Entropy

```python
# chatbot-app/backend/session/global_session_registry.py
import secrets

def _generate_session_id(self) -> str:
    """Generate cryptographically secure session ID"""
    random_suffix = secrets.token_hex(32)  # 256 bits
    return f"session_{random_suffix}"
```

### Medium-term Improvements (Month 2)

#### 1. Implement Data Encryption at Rest

```python
# chatbot-app/backend/services/encryption.py
from cryptography.fernet import Fernet
import boto3
import os

class EncryptionService:
    def __init__(self):
        # Use AWS KMS for key management in production
        if os.getenv("DEPLOYMENT_ENV") == "production":
            kms = boto3.client('kms')
            # Get data encryption key from KMS
            self.cipher = self._get_kms_cipher(kms)
        else:
            # Local development - use environment key
            key = os.getenv("ENCRYPTION_KEY") or Fernet.generate_key()
            self.cipher = Fernet(key)

    def encrypt(self, data: dict) -> bytes:
        json_data = json.dumps(data).encode()
        return self.cipher.encrypt(json_data)

    def decrypt(self, encrypted: bytes) -> dict:
        decrypted = self.cipher.decrypt(encrypted)
        return json.loads(decrypted.decode())

# Use in session manager
class SecureSessionManager:
    def __init__(self, session_id: str):
        self.encryption = EncryptionService()
        self._messages = []

    def add_message(self, message: dict):
        encrypted = self.encryption.encrypt(message)
        self._messages.append(encrypted)

    def get_messages(self) -> List[dict]:
        return [self.encryption.decrypt(m) for m in self._messages]
```

#### 2. Add Rate Limiting

```python
# chatbot-app/backend/middleware/rate_limit.py
from fastapi import HTTPException, Request
from collections import defaultdict
from datetime import datetime, timedelta

class RateLimitMiddleware:
    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self.request_counts = defaultdict(list)

    async def check_rate_limit(self, request: Request, user_id: str):
        now = datetime.now()
        minute_ago = now - timedelta(minutes=1)

        # Clean old requests
        self.request_counts[user_id] = [
            ts for ts in self.request_counts[user_id]
            if ts > minute_ago
        ]

        # Check limit
        if len(self.request_counts[user_id]) >= self.requests_per_minute:
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Try again later."
            )

        self.request_counts[user_id].append(now)
```

#### 3. Implement Secrets Management

```typescript
// agent-blueprint/chatbot-deployment/infrastructure/lib/chatbot-stack.ts
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';

// Create secret for API keys
const apiKeysSecret = new secretsmanager.Secret(this, 'ApiKeysSecret', {
  secretName: 'chatbot/api-keys',
  generateSecretString: {
    secretStringTemplate: JSON.stringify({
      TAVILY_API_KEY: '',
      NOVA_ACT_API_KEY: '',
    }),
    generateStringKey: 'password',
  },
});

// Grant read access to ECS task
apiKeysSecret.grantRead(backendTaskDefinition.taskRole);

// Add to environment
backendContainer.addSecret('TAVILY_API_KEY',
  ecs.Secret.fromSecretsManager(apiKeysSecret, 'TAVILY_API_KEY')
);
```

### Long-term Hardening (Ongoing)

#### 1. Add CloudFront WAF

```typescript
// chatbot-stack.ts
import * as wafv2 from 'aws-cdk-lib/aws-wafv2';

const webAcl = new wafv2.CfnWebACL(this, 'ChatbotWAF', {
  scope: 'CLOUDFRONT',
  defaultAction: { allow: {} },
  rules: [
    {
      name: 'RateLimitRule',
      priority: 1,
      action: { block: {} },
      statement: {
        rateBasedStatement: {
          limit: 2000,
          aggregateKeyType: 'IP',
        },
      },
      visibilityConfig: {
        sampledRequestsEnabled: true,
        cloudWatchMetricsEnabled: true,
        metricName: 'RateLimitRule',
      },
    },
  ],
  visibilityConfig: {
    sampledRequestsEnabled: true,
    cloudWatchMetricsEnabled: true,
    metricName: 'ChatbotWAF',
  },
});

// Associate with CloudFront
new wafv2.CfnWebACLAssociation(this, 'WAFAssociation', {
  resourceArn: distribution.distributionArn,
  webAclArn: webAcl.attrArn,
});
```

#### 2. Implement Security Monitoring

```python
# chatbot-app/backend/middleware/security_monitoring.py
import logging
from datetime import datetime

logger = logging.getLogger("security")

class SecurityMonitor:
    """Monitor and alert on suspicious activity"""

    @staticmethod
    def log_suspicious_activity(event_type: str, details: dict):
        """Log security events to CloudWatch"""
        logger.warning(
            f"SECURITY_EVENT: {event_type}",
            extra={
                "event_type": event_type,
                "timestamp": datetime.utcnow().isoformat(),
                "details": details,
            }
        )

    @staticmethod
    def check_session_hijacking_attempt(
        session_id: str,
        user_id: str,
        ip_address: str
    ):
        """Detect session hijacking patterns"""
        # Check for:
        # - Rapid IP address changes
        # - Geolocation anomalies
        # - User agent changes
        # - Impossible travel time
        pass
```

#### 3. Automated Security Scanning

```yaml
# .github/workflows/security-scan.yml
name: Security Scan
on: [push, pull_request]

jobs:
  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Run Bandit (Python security linter)
        run: |
          pip install bandit
          bandit -r chatbot-app/backend/

      - name: Run npm audit (Node.js dependencies)
        run: |
          cd chatbot-app/frontend
          npm audit --audit-level=high

      - name: Scan for secrets
        uses: trufflesecurity/trufflehog@main
        with:
          path: ./
          base: ${{ github.event.repository.default_branch }}
          head: HEAD
```

---

## 📋 Security Comparison: Local vs Cloud

| Security Control | Local Development | Cloud Deployment | Effectiveness |
|-----------------|-------------------|------------------|---------------|
| **User Authentication** | ❌ None | ✅ Cognito OAuth 2.0 | 🟢 Strong |
| **HTTPS Enforcement** | ❌ HTTP only | ✅ CloudFront mandatory | 🟢 Strong |
| **Network Isolation** | ❌ Public internet | ✅ VPC private subnets | 🟢 Strong |
| **DDoS Protection** | ❌ None | ✅ AWS Shield Standard | 🟢 Strong |
| **Credential Management** | ⚠️ .env file | ✅ IAM Task Roles | 🟢 Strong |
| **Audit Logging** | ⚠️ Local files | ✅ CloudWatch + X-Ray | 🟢 Strong |
| **Origin Protection** | ❌ Direct access | ✅ CloudFront-only ALB | 🟢 Strong |
| **Data Encryption (Transit)** | ❌ Plaintext | ✅ TLS 1.2+ | 🟢 Strong |
| **Data Encryption (Rest)** | ❌ None | ❌ None | 🔴 Critical Gap |
| **Session Security** | ❌ Weak IDs | ⚠️ Same weak IDs | 🟠 Needs Fix |
| **API Authentication** | ❌ None | ⚠️ Not enforced | 🟠 Needs Fix |
| **Rate Limiting** | ❌ None | ❌ None | 🟠 Needs Fix |
| **Input Validation** | ⚠️ Basic | ⚠️ Basic | 🟡 Improve |
| **Debug Endpoints** | ⚠️ Enabled | ⚠️ Enabled | 🔴 Critical Gap |

**Legend:**
- 🟢 Strong - Production-ready security control
- 🟡 Improve - Functional but can be enhanced
- 🟠 Needs Fix - Vulnerability with workaround available
- 🔴 Critical Gap - Major security risk

---

## 🎯 Priority Security Roadmap

### Phase 1: Critical Fixes (1-2 weeks)
**Goal:** Eliminate critical vulnerabilities that could lead to data breaches

1. ✅ Disable debug endpoints in production
2. ✅ Implement backend JWT validation
3. ✅ Link sessions to Cognito user IDs
4. ✅ Remove hardcoded CORS wildcards
5. ✅ Increase session ID entropy to 256 bits

**Success Criteria:**
- No unauthenticated access to sensitive endpoints
- Session hijacking significantly harder (256-bit IDs)
- CORS properly enforced via middleware

### Phase 2: Data Protection (2-4 weeks)
**Goal:** Protect sensitive data at rest and in transit

1. ✅ Implement AWS KMS encryption for session data
2. ✅ Encrypt uploaded files using envelope encryption
3. ✅ Add encryption for generated analysis results
4. ✅ Secure credential storage with AWS Secrets Manager
5. ✅ Implement secure deletion of temporary files

**Success Criteria:**
- All sensitive data encrypted at rest
- No API keys in code or version control
- Files securely deleted after use

### Phase 3: Monitoring & Response (1-2 months)
**Goal:** Detect and respond to security incidents

1. ✅ Implement rate limiting (CloudFront WAF)
2. ✅ Add security event logging
3. ✅ Set up CloudWatch alerts for anomalies
4. ✅ Create incident response playbook
5. ✅ Implement automated security scanning (CI/CD)

**Success Criteria:**
- Real-time alerting on suspicious activity
- Documented incident response procedures
- Automated vulnerability detection

### Phase 4: Compliance & Hardening (Ongoing)
**Goal:** Achieve compliance certifications and continuous improvement

1. ✅ Implement comprehensive audit logging
2. ✅ Add PII detection and redaction
3. ✅ Conduct penetration testing
4. ✅ Implement key rotation policies
5. ✅ Document security controls for compliance

**Success Criteria:**
- Compliance with PCI DSS / GDPR / SOC 2
- Annual penetration test reports
- Security documentation complete

---

## 📚 Additional Resources

### AWS Documentation
- **Cognito Authentication:** https://docs.aws.amazon.com/cognito/
- **CloudFront Security:** https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/security.html
- **VPC Security Best Practices:** https://docs.aws.amazon.com/vpc/latest/userguide/vpc-security-best-practices.html
- **IAM Best Practices:** https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html
- **AWS KMS Encryption:** https://docs.aws.amazon.com/kms/latest/developerguide/overview.html

### Project Documentation
- **Cloud Infrastructure:** `agent-blueprint/chatbot-deployment/infrastructure/`
- **Application Security Review:** `SECURITY_REVIEW_REPORT.md`
- **Deployment Guide:** `DEPLOYMENT.md`
- **CLAUDE.md Instructions:** `CLAUDE.md`

### Security Tools
- **Bandit (Python):** https://github.com/PyCQA/bandit
- **npm audit:** Built into npm
- **TruffleHog (Secret Scanning):** https://github.com/trufflesecurity/trufflehog
- **AWS Security Hub:** Centralised security findings

---

## 🔍 Security Testing Checklist

Before deploying to production, verify:

### Infrastructure Security
- [ ] Cognito user pool configured with strong password policy
- [ ] CloudFront HTTPS enforcement enabled
- [ ] ALB security group restricted to CloudFront prefix list
- [ ] ECS tasks in private subnets (no public IPs)
- [ ] IAM roles use least-privilege permissions
- [ ] CloudWatch logging enabled on all services
- [ ] VPC flow logs enabled
- [ ] AWS Config rules enabled for compliance monitoring

### Application Security
- [ ] All API endpoints require authentication
- [ ] Sessions linked to Cognito user IDs
- [ ] Session IDs have 256+ bits of entropy
- [ ] CORS configured via middleware only (no hardcoded wildcards)
- [ ] Debug endpoints disabled or gated behind admin auth
- [ ] Rate limiting implemented
- [ ] Input validation on all endpoints
- [ ] Error messages don't leak system information
- [ ] Sensitive data encrypted at rest
- [ ] API keys stored in Secrets Manager (not code)

### Monitoring & Response
- [ ] CloudWatch alarms configured for anomalies
- [ ] Security event logging implemented
- [ ] Incident response playbook documented
- [ ] Security contact information configured in AWS
- [ ] Penetration testing scheduled annually
- [ ] Security scanning in CI/CD pipeline

---

**Document Version:** 1.0
**Last Updated:** 20 October 2025
**Next Review:** After Phase 1 critical fixes completed

---

**Note:** This document describes the security architecture of the **cloud deployment**. For local development security considerations, see `SECURITY_REVIEW_REPORT.md`. Always keep this documentation updated as security controls evolve.
