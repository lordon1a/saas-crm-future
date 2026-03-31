# HTTP Request Action - Implementation Plan

## Overview
Adding a full-featured HTTP Request action node to the workflow system, similar to n8n's HTTP Request node.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (React)                         │
├─────────────────────────────────────────────────────────────┤
│  types.ts          - Add HttpRequestConfig type             │
│  nodeConfigs.ts    - Add http_request node config          │
│  NodePropertiesPanel - Already supports dynamic fields      │
│  api/workflows.ts  - Add test endpoint for HTTP request     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Backend (Flask)                         │
├─────────────────────────────────────────────────────────────┤
│  routes/workflows.py  - Add /api/v1/workflows/http-test   │
│  engine.py             - Execute HTTP request during workflow│
└─────────────────────────────────────────────────────────────┘
```

## Implementation Steps

### 1. Update types.ts
Add HTTP Request specific types:
```typescript
export type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
export type AuthType = 'none' | 'bearer' | 'basic' | 'api_key'

export interface HttpRequestConfig {
  url: string
  method: HttpMethod
  auth_type: AuthType
  headers?: Record<string, string>
  body?: string
  timeout?: number
}
```

### 2. Update nodeConfigs.ts
Add `http_request` node configuration:
```typescript
http_request: {
  label: 'Aksiyon',
  title: 'HTTP İsteği',
  icon: 'globe',
  faIcon: 'fa-globe',
  color: 'action',
  iconBg: '#6366f1',
  iconColor: '#ffffff',
  fields: [
    { key: 'url', label: 'URL', type: 'text', 
      placeholder: 'https://api.example.com/endpoint' },
    { key: 'method', label: 'HTTP Metodu', type: 'select', 
      options: [
        { value: 'GET', label: 'GET' },
        { value: 'POST', label: 'POST' },
        { value: 'PUT', label: 'PUT' },
        { value: 'PATCH', label: 'PATCH' },
        { value: 'DELETE', label: 'DELETE' }
      ]
    },
    { key: 'auth_type', label: 'Kimlik Doğrulama', type: 'select',
      options: [
        { value: 'none', label: 'Yok' },
        { value: 'bearer', label: 'Bearer Token' },
        { value: 'basic', label: 'Basic Auth' },
        { value: 'api_key', label: 'API Key' }
      ]
    },
    { key: 'header_key', label: 'Header Key', type: 'text',
      placeholder: 'Authorization' },
    { key: 'header_value', label: 'Header Value', type: 'text',
      placeholder: 'Bearer your-token-here' },
    { key: 'body', label: 'Body (JSON)', type: 'textarea',
      placeholder: '{"key": "{{contact.email}}"}' },
    { key: 'timeout', label: 'Timeout (saniye)', type: 'number', default: 30 }
  ]
}
```

### 3. Backend API Endpoint
Add test endpoint in routes/workflows.py:
```
POST /api/v1/workflows/http-test
Request: { url, method, headers, body, timeout }
Response: { success: boolean, status: number, data: any, error?: string }
```

### 4. Workflow Engine Integration
In engine.py, add HTTP request execution:
```python
async def execute_http_request(action_config):
    # Parse config
    # Apply auth headers
    # Execute request with timeout
    # Return response data
```

## File Changes Summary

| File | Changes |
|------|---------|
| `vite/workflow-ui/src/types.ts` | Add HttpRequestConfig interface |
| `vite/workflow-ui/src/constants/nodeConfigs.ts` | Add http_request node |
| `routes/workflows.py` | Add http-test endpoint |
| `engine.py` | Add execute_http_request method |

## Testing Plan
1. Create workflow with http_request node
2. Configure GET request to public API
3. Configure POST request with JSON body
4. Test authentication methods (Bearer, Basic, API Key)
5. Test timeout handling
6. Test error handling (invalid URL, timeouts)