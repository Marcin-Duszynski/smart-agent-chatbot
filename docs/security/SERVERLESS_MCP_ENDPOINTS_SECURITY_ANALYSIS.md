# Security Analysis: Serverless MCP Farm Endpoints

**✅ YES, the serverless MCP endpoints ARE secured.** Here's a comprehensive breakdown of the security mechanisms in place:

---

## 1. API Gateway Authentication (AWS IAM)

**Location**: `agent-blueprint/serverless-mcp-farm/*/infrastructure/cloudformation.yaml:83`

```yaml
AuthorizationType: AWS_IAM
```

**How it works:**
- All API Gateway methods (root, `/mcp`, and proxy paths) require **AWS IAM authentication**
- Clients must sign requests with valid AWS credentials using **AWS Signature Version 4 (SigV4)**
- Unauthenticated requests are automatically rejected at the API Gateway level

**Key configuration details:**
- Endpoint Type: **REGIONAL** (not EDGE, reducing attack surface)
- All three resources require authentication:
  - Root path (`/`)
  - MCP endpoint (`/mcp`)
  - Proxy catch-all (`/{proxy+}`)

---

## 2. SigV4 Request Signing for MCP Clients

**Location**: `chatbot-app/backend/mcp_sigv4_client.py`

The system includes a sophisticated **SigV4 authentication layer** for client-to-endpoint communication:

**Implementation details:**
- **SigV4HTTPXAuth class** (lines 31–70): Signs outbound HTTPX requests with AWS credentials
- **StreamableHTTPTransportWithSigV4 class** (lines 72–112): Extends MCP's StreamableHTTPTransport with cryptographic request signing
- **Credential handling** (lines 158–166): Automatically retrieves AWS credentials from default credential chain (IAM roles, environment variables, etc.)

**Security features:**
- Removes the `connection` header before signing (line 54) to prevent signature mismatches
- Includes the request body in the signature calculation
- Adds signed authentication headers to every outbound request

---

## 3. Automatic AWS Server Detection & Dynamic Authentication

**Location**: `chatbot-app/backend/mcp_client_factory.py:38–68`

The system **intelligently detects AWS endpoints** and applies the appropriate security:

```python
def is_aws_server(url: str) -> bool:
    aws_patterns = [
        "execute-api.amazonaws.com",
        "lambda-url.amazonaws.com",
        ".lambda-url.",
        ".execute-api."
    ]
    return any(pattern in url for pattern in aws_patterns)
```

**Workflow:**
1. **URL Pattern Detection** (line 115–130): Identifies AWS-hosted MCP servers
2. **Region Extraction** (line 133–147): Parses AWS region from URL (`us-west-2` format)
3. **Dynamic Service Identification** (line 47): Determines service type (execute-api vs lambda)
4. **Conditional Authentication** (line 52–56):
   - AWS servers → Use **SigV4 signing**
   - Non-AWS servers → Use **standard HTTP client**

---

## 4. AWS Parameter Store URL Resolution

**Location**: `chatbot-app/backend/mcp_client_factory.py:74–112`

MCP endpoint URLs support **AWS Systems Manager Parameter Store references** for secure secrets management:

```python
if not url.startswith('ssm://'):
    return url  # Regular URL

# Extract and resolve Parameter Store parameter
parameter_name = url[6:]  # Remove 'ssm://' prefix
response = ssm_client.get_parameter(Name=parameter_name)
resolved_url = response['Parameter']['Value']
```

**Benefit**: Sensitive MCP endpoint URLs are **never hardcoded**; they're stored in AWS Parameter Store and resolved at runtime.

---

## 5. IAM Role-Based Access Control

**Location**: `agent-blueprint/serverless-mcp-farm/*/infrastructure/cloudformation.yaml:19–42`

Each Lambda function has a **minimal IAM execution role**:

```yaml
LambdaExecutionRole:
  ManagedPolicyArns:
    - arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
  Policies:
    - Effect: Allow
      Action:
        - ssm:PutParameter
```

**Security principle**: Least privilege access—Lambda only has permissions to:
- Write CloudWatch logs (required for debugging)
- Update its own endpoint parameter in Parameter Store

---

## 6. Lambda Function URL Authorization (Implicit)

**Location**: `agent-blueprint/serverless-mcp-farm/*/infrastructure/cloudformation.yaml:86–87`

```yaml
Integration:
  Type: AWS_PROXY
  IntegrationHttpMethod: POST
  Uri: arn:aws:apigateway:...lambda:path/2015-03-31/functions/.../invocations
```

The Lambda invocation is gated by:
- **API Gateway IAM authentication** (first line of defence)
- **Lambda resource-based policy** (line 125–131) that only allows API Gateway invocations
- **SigV4 signing** for any cross-AWS-account access

---

## 7. Session Isolation & Credential Boundary

**Location**: `chatbot-app/backend/mcp_session_manager.py:32–83`

**Key security implication:**
- Each chat session has its own isolated MCP client instances
- Credentials used to connect to MCP servers are **AWS IAM credentials** of the Lambda/backend process
- User session IDs **cannot be used to bypass** MCP endpoint authentication

---

## 8. Transport Security

**Location**: Deploy scripts and CloudFormation:
- **HTTPS-only** API Gateway endpoints (URLs are always `https://...`)
- **AWS-managed TLS certificates** (automatic renewal)
- **SigV4 signatures include URL and method**, preventing tampering

---

## Threat Model Coverage

| Threat | Mitigation |
|--------|-----------|
| **Unauthenticated endpoint access** | AWS IAM authentication + SigV4 signing |
| **Request tampering** | SigV4 cryptographic signatures |
| **Credential exposure** | AWS temporary credentials (auto-rotated), Parameter Store for secrets |
| **Unauthorised service calls** | IAM role restrictions (minimal permissions) |
| **Cross-session data leakage** | Session-isolated MCP clients |
| **Man-in-the-middle attacks** | HTTPS + TLS (AWS-managed certificates) |
| **Replay attacks** | SigV4 includes timestamp + credentials |

---

## Credential Flow (Secure)

```
┌─────────────────┐
│  Backend        │
│  (Lambda Role)  │
└────────┬────────┘
         │ AWS credentials (temporary)
         ▼
┌─────────────────────────────────┐
│ MCPClientFactory                │
│ • Detects AWS server            │
│ • Extracts region               │
└────────┬────────────────────────┘
         │
         ▼
┌──────────────────────────────────┐
│ SigV4HTTPXAuth                   │
│ • Signs request with credentials │
│ • Adds Authorization header      │
└────────┬─────────────────────────┘
         │ Signed request
         ▼
┌──────────────────────────────────┐
│ API Gateway (AWS IAM)            │
│ • Verifies SigV4 signature       │
│ • Checks IAM permissions         │
└────────┬─────────────────────────┘
         │ Authenticated
         ▼
┌──────────────────────────────────┐
│ Lambda MCP Server                │
│ (Executes tool)                  │
└──────────────────────────────────┘
```

---

## Residual Security Considerations (Minor)

1. **Fallback to unsigned HTTP** (mcp_client_factory.py:61): If SigV4 client unavailable, it falls back to standard HTTP with a warning—only for non-AWS servers
2. **Parameter Store region hardcoded** (mcp_client_factory.py:98): Uses `us-west-2` for all SSM lookups; consider making this configurable
3. **Session timeout** (mcp_session_manager.py:29): 5 minutes timeout is reasonably aggressive, but worth reviewing for your use case

---

## Summary

**Security Architecture**: This system uses **defence-in-depth**: API Gateway IAM auth prevents unauthenticated access at the perimeter, whilst SigV4 signing ensures every request is cryptographically authenticated and tamper-proof. The automatic AWS server detection + role-based access means deployment configuration errors (missing SigV4) are visible immediately.

**Key Takeaway**: The MCP endpoints are **production-grade secure** with cryptographic authentication at every layer. No unauthenticated access is possible without valid AWS IAM credentials.

---

## File References

- API Gateway Configuration: `agent-blueprint/serverless-mcp-farm/aws-documentation/infrastructure/cloudformation.yaml`
- SigV4 Implementation: `chatbot-app/backend/mcp_sigv4_client.py`
- MCP Client Factory: `chatbot-app/backend/mcp_client_factory.py`
- Session Management: `chatbot-app/backend/mcp_session_manager.py`
- Cookie Security Middleware: `chatbot-app/backend/middleware/cookie_security.py`

---

**Report Generated**: 2025-10-20
