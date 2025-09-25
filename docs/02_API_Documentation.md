# MyTypist Backend API Documentation

## Overview

MyTypist provides a comprehensive RESTful API for document automation, template management, user authentication, payment processing, and system monitoring. All endpoints return JSON responses and use standard HTTP status codes.

## Base URL
- **Development**: `http://localhost:5000`
- **Production**: `https://your-domain.com`

## Authentication

### JWT Token-Based Authentication
All protected endpoints require a valid JWT token in the Authorization header:

```
Authorization: Bearer <your_jwt_token>
```

### Token Endpoints

#### Login
```http
POST /api/auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "your_password"
}
```

**Response:**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": {
    "id": 1,
    "email": "user@example.com",
    "full_name": "John Doe",
    "role": "user"
  }
}
```

#### Register
```http
POST /api/auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "secure_password",
  "full_name": "John Doe",
  "company_name": "Acme Corp"
}
```

#### Refresh Token
```http
POST /api/auth/refresh
Authorization: Bearer <refresh_token>
```

#### Get Current User
```http
GET /api/auth/me
Authorization: Bearer <access_token>
```

---

## Document Management

### Generate Document
```http
POST /api/documents/generate
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "template_id": 1,
  "placeholders": {
    "customer_name": "John Doe",
    "invoice_number": "INV-001",
    "date": "2025-01-15",
    "amount": "₦50,000"
  },
  "output_format": "pdf"
}
```

**Response:**
```json
{
  "document_id": 123,
  "download_url": "/api/documents/123/download",
  "file_name": "invoice_INV-001.pdf",
  "file_size": 245760,
  "generated_at": "2025-01-15T10:30:00Z",
  "expires_at": "2025-01-22T10:30:00Z"
}
```

### List Documents
```http
GET /api/documents?page=1&limit=20&search=invoice
Authorization: Bearer <access_token>
```

### Download Document
```http
GET /api/documents/{document_id}/download
Authorization: Bearer <access_token>
```

### Delete Document
```http
DELETE /api/documents/{document_id}
Authorization: Bearer <access_token>
```

---

## Template Management

### Upload Template
```http
POST /api/templates/upload
Authorization: Bearer <access_token>
Content-Type: multipart/form-data

{
  "file": <template.docx>,
  "name": "Invoice Template",
  "description": "Standard invoice template for Nigerian businesses"
}
```

### List Templates
```http
GET /api/templates?category=invoice&public=true
Authorization: Bearer <access_token>
```

### Get Template Details
```http
GET /api/templates/{template_id}
Authorization: Bearer <access_token>
```

**Response:**
```json
{
  "id": 1,
  "name": "Invoice Template",
  "description": "Standard invoice template",
  "placeholders": [
    {
      "name": "customer_name",
      "type": "text",
      "required": true,
      "description": "Customer full name"
    },
    {
      "name": "amount",
      "type": "currency",
      "required": true,
      "description": "Invoice amount in Naira"
    }
  ],
  "category": "invoice",
  "is_public": true,
  "created_at": "2025-01-15T10:00:00Z"
}
```

---

## Payment Processing

### Initiate Payment
```http
POST /api/payments/initiate
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "amount": 5000,
  "currency": "NGN",
  "payment_method": "card",
  "customer": {
    "email": "customer@example.com",
    "phone": "+2348012345678",
    "name": "John Doe"
  },
  "metadata": {
    "purpose": "document_generation",
    "documents_count": 5
  }
}
```

### Verify Payment
```http
GET /api/payments/{transaction_id}/verify
Authorization: Bearer <access_token>
```

### Payment History
```http
GET /api/payments/history?status=completed&limit=50
Authorization: Bearer <access_token>
```

---

## Digital Signatures

### Upload Signature
```http
POST /api/signatures/upload
Authorization: Bearer <access_token>
Content-Type: multipart/form-data

{
  "signature_file": <signature.png>,
  "signature_type": "image"
}
```

### Sign Document
```http
POST /api/documents/{document_id}/sign
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "signature_id": 1,
  "position": {
    "page": 1,
    "x": 100,
    "y": 200
  }
}
```

---

## System Monitoring

### Health Check
```http
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "service": "MyTypist Backend",
  "version": "1.0.0"
}
```

### Detailed Health Check
```http
GET /api/monitoring/health/detailed
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": 1705318200,
  "checks": {
    "database": {
      "status": "healthy",
      "pool_info": {
        "pool_utilization": 15.5,
        "active_connections": 3,
        "total_connections": 50
      }
    },
    "cache": {
      "status": "healthy"
    },
    "memory": {
      "status": "healthy",
      "stats": {
        "memory_usage_mb": 245.8,
        "memory_percent": 12.3
      }
    }
  }
}
```

### Performance Statistics (Admin Only)
```http
GET /api/monitoring/performance/stats
Authorization: Bearer <admin_access_token>
```

---

## Error Responses

### Standard Error Format
```json
{
  "detail": "Error message",
  "error_code": "VALIDATION_ERROR",
  "timestamp": "2025-01-15T10:30:00Z"
}
```

### Common HTTP Status Codes
- **200**: Success
- **201**: Created
- **400**: Bad Request (validation errors)
- **401**: Unauthorized (invalid/missing token)
- **403**: Forbidden (insufficient permissions)
- **404**: Not Found
- **413**: Payload Too Large (file too big)
- **429**: Too Many Requests (rate limit exceeded)
- **500**: Internal Server Error

---

## Rate Limits

| Endpoint Category | Limit | Window |
|------------------|-------|---------|
| Authentication | 5 requests | 5 minutes |
| Registration | 3 requests | 1 hour |
| Document Generation | 20 requests | 1 minute |
| File Upload | 10 requests | 1 minute |
| General API | 100 requests | 1 minute |

---

## File Upload Limits

- **Maximum file size**: 100MB
- **Supported formats**: .docx, .doc, .pdf, .xlsx, .pptx, .png, .jpg, .jpeg
- **Security**: All files are scanned for malicious content
- **Storage**: Files are encrypted at rest using AES-256

---

## Pagination

List endpoints support pagination with these parameters:
- **page**: Page number (starts from 1)
- **limit**: Items per page (max 100)
- **search**: Search query
- **sort**: Sort field
- **order**: Sort order (asc/desc)

**Example:**
```http
GET /api/documents?page=2&limit=20&search=invoice&sort=created_at&order=desc
```

---

## Webhooks

### Payment Webhook
MyTypist receives payment status updates from Flutterwave:

```http
POST /api/payments/webhook
Content-Type: application/json
X-Flw-Signature: <webhook_signature>

{
  "event": "charge.completed",
  "data": {
    "id": 123456,
    "tx_ref": "TXN_12345",
    "status": "successful",
    "amount": 5000,
    "currency": "NGN"
  }
}
```

### Signature Verification
All webhooks are verified using HMAC-SHA256 signature validation for security.

---

## SDKs and Integration

### JavaScript/TypeScript
```javascript
// API client example
const api = axios.create({
  baseURL: 'https://api.mytypist.com',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  }
});

// Generate document
const response = await api.post('/api/documents/generate', {
  template_id: 1,
  placeholders: {
    customer_name: 'John Doe',
    amount: '₦50,000'
  }
});
```

### Python
```python
import httpx

# API client
client = httpx.AsyncClient(
    base_url="https://api.mytypist.com",
    headers={"Authorization": f"Bearer {token}"}
)

# Generate document
response = await client.post("/api/documents/generate", json={
    "template_id": 1,
    "placeholders": {
        "customer_name": "John Doe",
        "amount": "₦50,000"
    }
})
```

---

## OpenAPI Documentation

Interactive API documentation is available at:
- **Swagger UI**: `/docs`
These endpoints provide comprehensive API exploration with example requests and responses.

## Analytics API

### Track Document Visit
```http
POST /api/analytics/track
Content-Type: application/json

{
  "document_id": 123,
  "visit_type": "view"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Visit tracked successfully",
  "visit_id": 456,
  "visit_metrics": {
    "session_quality_score": 0.85,
    "active_time_seconds": 300,
    "bounce": false,
    "created_at": "2025-09-14T10:30:00Z"
  }
}
```

### Get Visit Analytics
```http
GET /api/analytics/visits?document_id=123&days=30
Authorization: Bearer <your_jwt_token>
```

**Response:**
```json
{
  "total_visits": 1500,
  "unique_visitors": 850,
  "browser_stats": {
    "Chrome": 0.65,
    "Safari": 0.25,
    "Firefox": 0.10
  },
  "device_stats": {
    "desktop": 0.70,
    "mobile": 0.25,
    "tablet": 0.05
  },
  "avg_session_quality": 0.75,
  "bounce_rate": 0.25,
  "avg_active_time": 240
}
```

### Get Analytics Dashboard
```http
GET /api/analytics/dashboard-data
Authorization: Bearer <your_jwt_token>
```

**Response:**
```json
{
  "overview": {
    "total_documents": 100,
    "total_visits": 5000,
    "documents_today": 5,
    "visits_today": 150,
    "documents_this_week": 25,
    "visit_growth": 15.5,
    "avg_session_quality": 0.82,
    "avg_active_time": 280,
    "bounce_rate": 0.22
  },
  "top_documents": [
    {
      "id": 123,
      "title": "Sample Document",
      "visits": 500
    }
  ],
  "template_usage": [
    {
      "id": 456,
      "name": "Business Letter",
      "usage_count": 200
    }
  ],
  "device_stats": {
    "desktop": 0.68,
    "mobile": 0.27,
    "tablet": 0.05
  }
}
```

### Export Analytics Data
```http
GET /api/analytics/export?format=json&document_id=123&days=30
Authorization: Bearer <your_jwt_token>
```

**Response (JSON format):**
```json
{
  "format": "json",
  "export_date": "2025-09-14T10:30:00Z",
  "period_days": 30,
  "total_records": 500,
  "visits": [
    {
      "visit_id": 789,
      "document_id": 123,
      "visit_type": "view",
      "visitor_info": {
        "country": "US",
        "city": "New York",
        "device_type": "desktop",
        "browser": "Chrome",
        "os": "Windows"
      },
      "engagement": {
        "session_quality_score": 0.85,
        "active_time_seconds": 300,
        "bounce": false
      },
      "created_at": "2025-09-14T10:00:00Z"
    }
  ]
}
```

### Anonymize Analytics Data
```http
POST /api/analytics/anonymize
Authorization: Bearer <your_jwt_token>
Content-Type: application/json

{
  "document_id": 123  // Optional - if not provided, anonymizes all user's data
}
```

**Response:**
```json
{
  "success": true,
  "anonymized_count": 500,
  "message": "Successfully anonymized analytics data"
}
```

### Analytics Performance Guidelines

#### Response Times
- Track visit: < 100ms
- Get analytics: < 500ms
- Export data: < 1000ms for up to 10,000 records

#### Rate Limits
- Track endpoint: 100 requests per minute per IP
- Dashboard data: 60 requests per minute per user
- Export data: 10 requests per minute per user

#### Data Retention
- Raw visit data: 90 days
- Aggregated metrics: 2 years
- Anonymized data: Indefinitely

#### Caching
The analytics service uses multi-level caching:
- L1 cache (memory): 5 minutes
- L2 cache (Redis): 30 minutes
- Dashboard data: 5 minutes
- Aggregated metrics: 15 minutes


# 🚀 **NEW API ENDPOINTS DOCUMENTATION**

## **Overview**

This document details all the new API endpoints added during the comprehensive backend audit and enhancement. These endpoints provide enterprise-grade functionality for template marketplace, wallet management, document editing, advanced search, and notifications.

---

## **Template Discovery & Usage API**
All marketplace functionality has been consolidated into the templates APIs.
**Base URL**: `/api/templates`

### **Public Endpoints**

#### `GET /home`
Get templates homepage with featured, trending, and new templates.
```json
{
  "featured_templates": [...],
  "trending_templates": [...],
  "new_templates": [...],
  "categories": [...],
  "featured_collections": [...],
  "recent_purchases": [...]
}
```

#### `GET /search`
Advanced template search with filtering and sorting (use `/api/templates/search`).
**Query Parameters:**
- `query`: Search query string
- `category`: Filter by category
- `min_price`, `max_price`: Price range filters
- `rating`: Minimum rating filter
- `sort_by`: Sort order (relevance, price_low, price_high, rating, popularity, newest)
- `page`, `per_page`: Pagination

#### `GET /{template_id}`
Get detailed template information including reviews and related templates (use `/api/templates/{template_id}`).

### **User Actions**

#### `POST /{template_id}/purchase`
Purchase or charge tokens for a template using wallet or token-based flow (use `/api/templates/{template_id}/purchase`).
```json
{
  "payment_method": "wallet"
}
```

#### `POST /{template_id}/review`
Add or update a template review (use `/api/templates/{template_id}/review`).
**Query Parameters:**
- `rating`: 1-5 star rating
- `title`: Review title (optional)
- `comment`: Review comment (optional)

#### `POST /{template_id}/favorite`
Toggle template favorite status (use `/api/templates/{template_id}/favorite`).

### **User Management**

#### `GET /my/purchases`
Get user's template purchase history with pagination (use `/api/templates/my/purchases`).

#### `GET /my/favorites`
Get user's favorite templates with pagination (use `/api/templates/my/favorites`).

#### `GET /stats`
Get templates statistics and analytics (use `/api/templates/stats`).

---

## **💰 Wallet & Transactions API**
**Base URL**: `/api/wallet`

### **Wallet Management**

#### `GET /balance`
Get wallet balance and information.
```json
{
  "wallet_id": 123,
  "balance": 5000.00,
  "pending_balance": 0.00,
  "total_earned": 10000.00,
  "total_spent": 5000.00,
  "currency": "NGN",
  "is_active": true,
  "is_frozen": false,
  "daily_spend_limit": 2000.00,
  "monthly_spend_limit": 50000.00,
  "daily_spent": 100.00,
  "monthly_spent": 1500.00
}
```

#### `POST /add-funds`
Add funds to wallet (integrates with payment gateway).
```json
{
  "amount": 1000.00,
  "description": "Wallet top-up",
  "payment_reference": "PAY_123456"
}
```

#### `POST /transfer`
Transfer funds to another user.
```json
{
  "recipient_user_id": 456,
  "amount": 500.00,
  "description": "Payment for services",
  "reference": "TRANSFER_789"
}
```

### **Transaction Management**

#### `GET /transactions`
Get wallet transaction history with filtering.
**Query Parameters:**
- `page`, `per_page`: Pagination
- `transaction_type`: Filter by type (credit, debit, transfer_in, transfer_out, refund)
- `start_date`, `end_date`: Date range filters

#### `POST /transactions/{transaction_id}/refund`
Request refund for a transaction.
```json
{
  "reason": "Service not delivered"
}
```

### **Settings & Analytics**

#### `POST /settings/limits`
Set wallet spending limits.
```json
{
  "daily_limit": 2000.00,
  "monthly_limit": 50000.00
}
```

#### `GET /statistics`
Get wallet usage statistics and spending patterns.
**Query Parameters:**
- `days`: Number of days for statistics (default: 30)

---

## **✏️ Document Editing API**
**Base URL**: `/api/documents`

### **Edit Management**

#### `POST /{document_id}/estimate-edit-cost`
Estimate the cost of editing a document based on placeholder changes.
```json
{
  "new_placeholder_data": {
    "name": "John Doe",
    "age": "30",
    "address": "123 Main St",
    "phone": "+234-xxx-xxxx"
  }
}
```

**Response:**
```json
{
  "document_id": 123,
  "total_changes": 4,
  "free_changes_allowed": 3,
  "is_free_edit": false,
  "cost": 100.00,
  "currency": "NGN",
  "requires_payment": true,
  "changes_breakdown": {...}
}
```

#### `POST /{document_id}/edit`
Apply edits to a document with automatic pricing.
```json
{
  "new_placeholder_data": {...},
  "edit_reason": "Updated client information",
  "force_payment": false
}
```

**Response:**
```json
{
  "success": true,
  "document_id": 124,  // New document ID if paid edit
  "edit_id": 456,
  "changes_applied": 4,
  "is_free_edit": false,
  "charge_applied": 100.00,
  "payment_transaction_id": 789,
  "created_new_document": true,
  "message": "Document edited successfully (new document created due to paid edit)"
}
```

### **Edit History**

#### `GET /{document_id}/edit-history`
Get edit history for a document.

#### `POST /edits/{edit_id}/revert`
Revert a document edit (with refund if applicable).

### **User Analytics**

#### `GET /my/edit-statistics`
Get user's document editing statistics.
**Query Parameters:**
- `days`: Number of days for statistics (default: 30)

#### `GET /pricing-info`
Get current edit pricing information and policies.

---

## **🔍 Advanced Search API**
**Base URL**: `/api/search`

### **Search Endpoints**

#### `GET /templates`
Advanced template search with full-text search and ranking.
**Query Parameters:**
- `query`: Search query
- `category`, `min_price`, `max_price`, `rating`, `language`: Filters
- `tags`: Array of tags to filter by
- `sort_by`: Sort order
- `page`, `per_page`: Pagination

**Response includes:**
- Search results with relevance scoring
- Search suggestions
- Performance metrics (response time)
- Applied filters summary

#### `GET /documents`
Advanced document search for user's documents.
**Query Parameters:**
- `query`: Search query (required)
- `status`, `template_id`: Filters
- `start_date`, `end_date`: Date range filters
- `sort_by`: Sort order
- `page`, `per_page`: Pagination

### **Recommendations**

#### `GET /recommendations`
Get personalized search recommendations based on user behavior.
**Query Parameters:**
- `limit`: Number of recommendations (default: 10, max: 50)

**Response:**
```json
{
  "recommendations": [
    {
      "type": "template",
      "item": {...},
      "reason": "Popular among similar users",
      "score": 0.85
    }
  ],
  "total": 5,
  "generated_at": "2024-12-01T10:00:00Z"
}
```

### **Analytics**

#### `GET /analytics`
Get search analytics for the user.
**Query Parameters:**
- `days`: Number of days for analytics (default: 30)

#### `GET /global/analytics` *(Admin Only)*
Get global search analytics across all users.

---

## **🔔 Notifications API**
**Base URL**: `/api/notifications`

### **Notification Management**

#### `GET /`
Get user's notifications with filtering and pagination.
**Query Parameters:**
- `page`, `per_page`: Pagination
- `unread_only`: Show only unread notifications
- `notification_type`: Filter by type

**Response:**
```json
{
  "notifications": [...],
  "total": 25,
  "unread_count": 5,
  "page": 1,
  "per_page": 20,
  "pages": 2
}
```

#### `POST /{notification_id}/read`
Mark a specific notification as read.

#### `POST /mark-all-read`
Mark all notifications (or specific type) as read.
```json
{
  "notification_type": "security_alert"  // Optional
}
```

#### `DELETE /{notification_id}`
Dismiss/delete a notification.

### **Analytics & Settings**

#### `GET /statistics`
Get notification statistics for the user.
**Query Parameters:**
- `days`: Number of days for statistics

#### `POST /test` *(Development Only)*
Create a test notification for development/testing.
```json
{
  "title": "Test Notification",
  "message": "This is a test notification",
  "notification_type": "system_maintenance",
  "priority": "medium"
}
```

---

## **📊 Enhanced Analytics Endpoints**

### **Template Analytics**
- Template performance metrics
- Sales and revenue tracking
- Popular categories and trends
- User engagement metrics

### **Wallet Analytics**
- Transaction patterns and trends
- Spending behavior analysis
- Revenue tracking by source
- User financial activity

### **Search Analytics**
- Query performance and patterns
- Popular search terms
- Recommendation effectiveness
- User search behavior

### **Notification Analytics**
- Delivery success rates
- User engagement metrics
- Channel performance
- Notification preferences

---

## **🔐 Security Features**

### **Authentication**
All endpoints require valid JWT token in Authorization header:
```
Authorization: Bearer <jwt_token>
```

### **Rate Limiting**
- **Standard**: 100 requests per minute per user
- **Search**: 50 requests per minute per user
- **Wallet**: 20 requests per minute per user

### **Input Validation**
- All inputs validated and sanitized
- SQL injection protection
- XSS prevention
- CSRF protection for state-changing operations

### **Audit Logging**
All API calls are logged with:
- User identification
- Request details
- Response status
- Performance metrics
- Security events

---

## **📈 Performance Characteristics**

### **Response Times**
- **Simple queries**: < 100ms
- **Search operations**: < 500ms
- **Complex analytics**: < 1000ms
- **File operations**: < 5000ms

### **Pagination**
- Default page size: 20 items
- Maximum page size: 100 items
- Efficient cursor-based pagination for large datasets

### **Caching**
- Template data cached for 5 minutes
- Search results cached for 1 minute
- User data cached for 10 minutes
- Analytics cached for 1 hour

---

## **🚀 Integration Examples**

### **Frontend Integration**
```javascript
// Search templates
const searchTemplates = async (query) => {
  const response = await fetch(`/api/templates/search?query=${query}`, {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  return response.json();
};

// Purchase template
const purchaseTemplate = async (templateId) => {
  const response = await fetch(`/api/templates/${templateId}/purchase`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ payment_method: 'wallet' })
  });
  return response.json();
};

// Edit document
const editDocument = async (documentId, placeholderData) => {
  const response = await fetch(`/api/documents/${documentId}/edit`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ new_placeholder_data: placeholderData })
  });
  return response.json();
};
```

### **Mobile App Integration**
```swift
// iOS Swift example
func searchTemplates(query: String) async throws -> SearchResponse {
  let url = URL(string: "\(baseURL)/api/templates/search?query=\(query)")!
    var request = URLRequest(url: url)
    request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")

    let (data, _) = try await URLSession.shared.data(for: request)
    return try JSONDecoder().decode(SearchResponse.self, from: data)
}
```

---

## **📋 Error Handling**

### **Standard Error Response**
```json
{
  "error": "validation_error",
  "message": "Invalid input data",
  "details": {
    "field": "amount",
    "reason": "Must be greater than 0"
  },
  "request_id": "req_123456"
}
```

### **Common Error Codes**
- `400`: Bad Request - Invalid input
- `401`: Unauthorized - Invalid or missing token
- `403`: Forbidden - Insufficient permissions
- `404`: Not Found - Resource doesn't exist
- `429`: Too Many Requests - Rate limit exceeded
- `500`: Internal Server Error - System error

---

## **🎯 Best Practices**

### **API Usage**
1. **Always handle errors gracefully**
2. **Implement proper retry logic for transient failures**
3. **Use pagination for list endpoints**
4. **Cache responses when appropriate**
5. **Implement proper loading states**

### **Security**
1. **Never log or store JWT tokens**
2. **Validate all user inputs on frontend**
3. **Implement proper CSRF protection**
4. **Use HTTPS in production**
5. **Handle sensitive data appropriately**

### **Performance**
1. **Use appropriate page sizes**
2. **Implement client-side caching**
3. **Debounce search queries**
4. **Use WebSockets for real-time updates**
5. **Optimize images and assets**

---

**Documentation Updated**: December 2024
**API Version**: v1.0
**Status**: ✅ **Production Ready**
