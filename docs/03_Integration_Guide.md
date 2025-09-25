    ` ``````````  # Frontend Integration Guide

## Overview

This guide provides comprehensive instructions for integrating frontend applications with the MyTypist Backend API. The backend is designed to work seamlessly with any frontend framework including React, Vue.js, Angular, and mobile applications.

## API Base Configuration

### 1. API Client Setup

#### React/JavaScript
```javascript
// api/client.js
import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:5000';

// Create axios instance
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor for authentication
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor for token refresh
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      // Try to refresh token
      const refreshToken = localStorage.getItem('refresh_token');
      if (refreshToken) {
        try {
          const response = await axios.post(`${API_BASE_URL}/api/auth/refresh`, {}, {
            headers: { Authorization: `Bearer ${refreshToken}` }
          });
          
          const { access_token } = response.data;
          localStorage.setItem('access_token', access_token);
          
          // Retry original request
          error.config.headers.Authorization = `Bearer ${access_token}`;
          return apiClient.request(error.config);
        } catch (refreshError) {
          // Refresh failed, redirect to login
          localStorage.clear();
          window.location.href = '/login';
        }
      }
    }
    return Promise.reject(error);
  }
);

export default apiClient;
```

#### Vue.js
```javascript
// plugins/api.js
import axios from 'axios';
import { useAuthStore } from '@/stores/auth';

const api = axios.create({
  baseURL: process.env.VUE_APP_API_URL || 'http://localhost:5000',
  timeout: 30000,
});

api.interceptors.request.use((config) => {
  const authStore = useAuthStore();
  if (authStore.token) {
    config.headers.Authorization = `Bearer ${authStore.token}`;
  }
  return config;
});

export default api;
```

#### Angular
```typescript
// services/api.service.ts
import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders, HttpInterceptor } from '@angular/common/http';
import { Observable } from 'rxjs';

@Injectable({
  providedIn: 'root'
})
export class ApiService {
  private baseUrl = environment.apiUrl || 'http://localhost:5000';

  constructor(private http: HttpClient) {}

  private getHeaders(): HttpHeaders {
    const token = localStorage.getItem('access_token');
    return new HttpHeaders({
      'Content-Type': 'application/json',
      ...(token && { Authorization: `Bearer ${token}` })
    });
  }

  get<T>(endpoint: string): Observable<T> {
    return this.http.get<T>(`${this.baseUrl}${endpoint}`, {
      headers: this.getHeaders()
    });
  }

  post<T>(endpoint: string, data: any): Observable<T> {
    return this.http.post<T>(`${this.baseUrl}${endpoint}`, data, {
      headers: this.getHeaders()
    });
  }
}
```

---

## Authentication Integration

### 1. Login Flow
```javascript
// services/auth.js
import apiClient from './client';

export const authService = {
  async login(email, password) {
    try {
      const response = await apiClient.post('/api/auth/login', {
        email,
        password
      });
      
      const { access_token, refresh_token, user } = response.data;
      
      // Store tokens
      localStorage.setItem('access_token', access_token);
      localStorage.setItem('refresh_token', refresh_token);
      localStorage.setItem('user', JSON.stringify(user));
      
      return { user, success: true };
    } catch (error) {
      return {
        success: false,
        error: error.response?.data?.detail || 'Login failed'
      };
    }
  },

  async register(userData) {
    try {
      const response = await apiClient.post('/api/auth/register', userData);
      return { success: true, data: response.data };
    } catch (error) {
      return {
        success: false,
        error: error.response?.data?.detail || 'Registration failed'
      };
    }
  },

  async getCurrentUser() {
    try {
      const response = await apiClient.get('/api/auth/me');
      return response.data;
    } catch (error) {
      throw error;
    }
  },

  logout() {
    localStorage.clear();
    window.location.href = '/login';
  }
};
```

### 2. React Authentication Hook
```javascript
// hooks/useAuth.js
import { useState, useEffect, createContext, useContext } from 'react';
import { authService } from '../services/auth';

const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const initAuth = async () => {
      const token = localStorage.getItem('access_token');
      if (token) {
        try {
          const userData = await authService.getCurrentUser();
          setUser(userData);
        } catch (error) {
          localStorage.clear();
        }
      }
      setLoading(false);
    };

    initAuth();
  }, []);

  const login = async (email, password) => {
    const result = await authService.login(email, password);
    if (result.success) {
      setUser(result.user);
    }
    return result;
  };

  const logout = () => {
    authService.logout();
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, login, logout, loading }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};
```

---

## Document Generation Integration

### 1. Template Selection Component
```javascript
// components/TemplateSelector.jsx
import React, { useState, useEffect } from 'react';
import apiClient from '../services/client';

const TemplateSelector = ({ onTemplateSelect }) => {
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchTemplates = async () => {
      try {
        const response = await apiClient.get('/api/templates');
        setTemplates(response.data.templates);
      } catch (error) {
        console.error('Failed to fetch templates:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchTemplates();
  }, []);

  return (
    <div className="template-selector">
      <h3>Select a Template</h3>
      {loading ? (
        <div>Loading templates...</div>
      ) : (
        <div className="template-grid">
          {templates.map((template) => (
            <div
              key={template.id}
              className="template-card"
              onClick={() => onTemplateSelect(template)}
            >
              <h4>{template.name}</h4>
              <p>{template.description}</p>
              <small>{template.category}</small>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default TemplateSelector;
```

### 2. Document Generation Form
```javascript
// components/DocumentGenerator.jsx
import React, { useState } from 'react';
import apiClient from '../services/client';

const DocumentGenerator = ({ template }) => {
  const [placeholders, setPlaceholders] = useState({});
  const [generating, setGenerating] = useState(false);

  const handlePlaceholderChange = (name, value) => {
    setPlaceholders(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const generateDocument = async () => {
    setGenerating(true);
    
    try {
      const response = await apiClient.post('/api/documents/generate', {
        template_id: template.id,
        placeholders: placeholders,
        output_format: 'pdf'
      });

      // Download generated document
      const downloadUrl = response.data.download_url;
      window.open(`${apiClient.defaults.baseURL}${downloadUrl}`, '_blank');
    } catch (error) {
      console.error('Document generation failed:', error);
      alert('Failed to generate document. Please try again.');
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div className="document-generator">
      <h3>Generate Document: {template.name}</h3>
      
      <form onSubmit={(e) => { e.preventDefault(); generateDocument(); }}>
        {template.placeholders.map((placeholder) => (
          <div key={placeholder.name} className="form-group">
            <label htmlFor={placeholder.name}>
              {placeholder.description || placeholder.name}
              {placeholder.required && <span className="required">*</span>}
            </label>
            
            <input
              type={placeholder.type === 'currency' ? 'number' : 'text'}
              id={placeholder.name}
              required={placeholder.required}
              onChange={(e) => handlePlaceholderChange(placeholder.name, e.target.value)}
              placeholder={`Enter ${placeholder.name}`}
            />
          </div>
        ))}
        
        <button type="submit" disabled={generating}>
          {generating ? 'Generating...' : 'Generate Document'}
        </button>
      </form>
    </div>
  );
};

export default DocumentGenerator;
```

---

## File Upload Integration

### 1. Template Upload Component
```javascript
// components/TemplateUpload.jsx
import React, { useState } from 'react';
import apiClient from '../services/client';

const TemplateUpload = ({ onUploadSuccess }) => {
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);

  const handleFileUpload = async (event) => {
    event.preventDefault();
    
    if (!file) return;

    setUploading(true);
    setUploadProgress(0);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('name', file.name.replace(/\.[^/.]+$/, ""));
    formData.append('description', 'Custom template');

    try {
      const response = await apiClient.post('/api/templates/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        onUploadProgress: (progressEvent) => {
          const progress = Math.round(
            (progressEvent.loaded / progressEvent.total) * 100
          );
          setUploadProgress(progress);
        },
      });

      onUploadSuccess(response.data);
      setFile(null);
    } catch (error) {
      console.error('Upload failed:', error);
      alert('Template upload failed. Please try again.');
    } finally {
      setUploading(false);
      setUploadProgress(0);
    }
  };

  return (
    <div className="template-upload">
      <h3>Upload Template</h3>
      
      <form onSubmit={handleFileUpload}>
        <div className="file-input">
          <input
            type="file"
            accept=".docx,.doc"
            onChange={(e) => setFile(e.target.files[0])}
            required
          />
        </div>
        
        {uploading && (
          <div className="progress-bar">
            <div 
              className="progress-fill" 
              style={{ width: `${uploadProgress}%` }}
            >
              {uploadProgress}%
            </div>
          </div>
        )}
        
        <button type="submit" disabled={!file || uploading}>
          {uploading ? 'Uploading...' : 'Upload Template'}
        </button>
      </form>
    </div>
  );
};

export default TemplateUpload;
```

---

## Payment Integration

### 1. Payment Flow Component
```javascript
// components/PaymentFlow.jsx
import React, { useState } from 'react';
import apiClient from '../services/client';

const PaymentFlow = ({ amount, onPaymentSuccess }) => {
  const [paymentMethods] = useState(['card', 'bank_transfer', 'ussd', 'mobile_money']);
  const [selectedMethod, setSelectedMethod] = useState('card');
  const [processing, setProcessing] = useState(false);

  const initiatePayment = async () => {
    setProcessing(true);

    try {
      const paymentData = {
        amount: amount,
        currency: 'NGN',
        payment_method: selectedMethod,
        customer: {
          email: user.email,
          name: user.full_name,
          phone: user.phone
        },
        metadata: {
          purpose: 'document_generation',
          user_id: user.id
        }
      };

      const response = await apiClient.post('/api/payments/initiate', paymentData);
      
      // Redirect to Flutterwave payment page
      window.location.href = response.data.payment_url;
    } catch (error) {
      console.error('Payment initiation failed:', error);
      alert('Payment failed to initiate. Please try again.');
    } finally {
      setProcessing(false);
    }
  };

  return (
    <div className="payment-flow">
      <h3>Pay ₦{amount.toLocaleString()}</h3>
      
      <div className="payment-methods">
        {paymentMethods.map((method) => (
          <label key={method} className="payment-method">
            <input
              type="radio"
              value={method}
              checked={selectedMethod === method}
              onChange={(e) => setSelectedMethod(e.target.value)}
            />
            <span>{method.replace('_', ' ').toUpperCase()}</span>
          </label>
        ))}
      </div>
      
      <button onClick={initiatePayment} disabled={processing}>
        {processing ? 'Processing...' : 'Pay Now'}
      </button>
    </div>
  );
};

export default PaymentFlow;
```

---

## Real-time Features

### 1. WebSocket Integration (Optional)
```javascript
// services/websocket.js
class WebSocketService {
  constructor() {
    this.ws = null;
    this.listeners = new Map();
  }

  connect(token) {
    const wsUrl = `ws://localhost:5000/ws?token=${token}`;
    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = () => {
      console.log('WebSocket connected');
    };

    this.ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      this.notifyListeners(data.type, data.payload);
    };

    this.ws.onclose = () => {
      console.log('WebSocket disconnected');
      // Implement reconnection logic
    };
  }

  subscribe(eventType, callback) {
    if (!this.listeners.has(eventType)) {
      this.listeners.set(eventType, []);
    }
    this.listeners.get(eventType).push(callback);
  }

  notifyListeners(eventType, data) {
    const callbacks = this.listeners.get(eventType) || [];
    callbacks.forEach(callback => callback(data));
  }
}

export default new WebSocketService();
```

### 2. Document Generation Progress
```javascript
// hooks/useDocumentGeneration.js
import { useState, useEffect } from 'react';
import apiClient from '../services/client';

export const useDocumentGeneration = () => {
  const [generationStatus, setGenerationStatus] = useState(null);

  const generateDocument = async (templateId, placeholders) => {
    try {
      setGenerationStatus({ status: 'starting', progress: 0 });
      
      const response = await apiClient.post('/api/documents/generate', {
        template_id: templateId,
        placeholders: placeholders
      });

      if (response.data.status === 'processing') {
        // Poll for completion
        pollGenerationStatus(response.data.task_id);
      } else {
        setGenerationStatus({
          status: 'completed',
          progress: 100,
          document: response.data
        });
      }
    } catch (error) {
      setGenerationStatus({
        status: 'error',
        error: error.response?.data?.detail || 'Generation failed'
      });
    }
  };

  const pollGenerationStatus = async (taskId) => {
    const poll = async () => {
      try {
        const response = await apiClient.get(`/api/documents/status/${taskId}`);
        const { status, progress, document } = response.data;

        setGenerationStatus({ status, progress });

        if (status === 'completed') {
          setGenerationStatus({
            status: 'completed',
            progress: 100,
            document
          });
        } else if (status === 'failed') {
          setGenerationStatus({
            status: 'error',
            error: 'Document generation failed'
          });
        } else {
          // Continue polling
          setTimeout(poll, 1000);
        }
      } catch (error) {
        setGenerationStatus({
          status: 'error',
          error: 'Failed to check generation status'
        });
      }
    };

    poll();
  };

  return { generationStatus, generateDocument };
};
```

---

## State Management

### 1. Redux Toolkit (React)
```javascript
// store/slices/documentsSlice.js
import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import apiClient from '../../services/client';

export const fetchDocuments = createAsyncThunk(
  'documents/fetchDocuments',
  async ({ page = 1, limit = 20, search = '' }) => {
    const response = await apiClient.get(
      `/api/documents?page=${page}&limit=${limit}&search=${search}`
    );
    return response.data;
  }
);

export const generateDocument = createAsyncThunk(
  'documents/generateDocument',
  async ({ templateId, placeholders }) => {
    const response = await apiClient.post('/api/documents/generate', {
      template_id: templateId,
      placeholders: placeholders
    });
    return response.data;
  }
);

const documentsSlice = createSlice({
  name: 'documents',
  initialState: {
    documents: [],
    loading: false,
    error: null,
    pagination: {
      page: 1,
      totalPages: 1,
      totalItems: 0
    }
  },
  reducers: {
    clearError: (state) => {
      state.error = null;
    }
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchDocuments.pending, (state) => {
        state.loading = true;
      })
      .addCase(fetchDocuments.fulfilled, (state, action) => {
        state.loading = false;
        state.documents = action.payload.documents;
        state.pagination = action.payload.pagination;
      })
      .addCase(fetchDocuments.rejected, (state, action) => {
        state.loading = false;
        state.error = action.error.message;
      });
  }
});

export const { clearError } = documentsSlice.actions;
export default documentsSlice.reducer;
```

### 2. Pinia Store (Vue.js)
```javascript
// stores/documents.js
import { defineStore } from 'pinia';
import api from '../plugins/api';

export const useDocumentsStore = defineStore('documents', {
  state: () => ({
    documents: [],
    templates: [],
    loading: false,
    error: null
  }),

  actions: {
    async fetchDocuments(params = {}) {
      this.loading = true;
      try {
        const response = await api.get('/api/documents', { params });
        this.documents = response.data.documents;
      } catch (error) {
        this.error = error.response?.data?.detail || 'Failed to fetch documents';
      } finally {
        this.loading = false;
      }
    },

    async generateDocument(templateId, placeholders) {
      this.loading = true;
      try {
        const response = await api.post('/api/documents/generate', {
          template_id: templateId,
          placeholders
        });
        return response.data;
      } catch (error) {
        this.error = error.response?.data?.detail || 'Generation failed';
        throw error;
      } finally {
        this.loading = false;
      }
    }
  }
});
```

---

## Error Handling

### 1. Global Error Handler
```javascript
// utils/errorHandler.js
export const handleApiError = (error) => {
  if (error.response) {
    // Server responded with error status
    const { status, data } = error.response;
    
    switch (status) {
      case 400:
        return data.detail || 'Invalid request data';
      case 401:
        // Handle authentication error
        localStorage.clear();
        window.location.href = '/login';
        return 'Session expired. Please login again.';
      case 403:
        return 'You do not have permission for this action';
      case 404:
        return 'Resource not found';
      case 429:
        return 'Too many requests. Please wait and try again.';
      case 500:
        return 'Server error. Please try again later.';
      default:
        return data.detail || 'An unexpected error occurred';
    }
  } else if (error.request) {
    // Network error
    return 'Network error. Please check your connection.';
  } else {
    // Other error
    return error.message || 'An unexpected error occurred';
  }
};
```

### 2. Error Boundary (React)
```javascript
// components/ErrorBoundary.jsx
import React from 'react';

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('Application error:', error, errorInfo);
    
    // Send error to monitoring service
    if (window.Sentry) {
      window.Sentry.captureException(error);
    }
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="error-boundary">
          <h2>Something went wrong</h2>
          <p>We're sorry, but something unexpected happened.</p>
          <button onClick={() => window.location.reload()}>
            Reload Page
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
```

---

## Performance Optimization

### 1. API Response Caching
```javascript
// utils/cache.js
class ApiCache {
  constructor() {
    this.cache = new Map();
    this.defaultTTL = 5 * 60 * 1000; // 5 minutes
  }

  set(key, data, ttl = this.defaultTTL) {
    const expiry = Date.now() + ttl;
    this.cache.set(key, { data, expiry });
  }

  get(key) {
    const item = this.cache.get(key);
    if (!item) return null;

    if (Date.now() > item.expiry) {
      this.cache.delete(key);
      return null;
    }

    return item.data;
  }

  clear() {
    this.cache.clear();
  }
}

export default new ApiCache();
```

### 2. Lazy Loading Components
```javascript
// Lazy load heavy components
import { lazy, Suspense } from 'react';

const DocumentEditor = lazy(() => import('./DocumentEditor'));
const PaymentForm = lazy(() => import('./PaymentForm'));

const App = () => {
  return (
    <div className="app">
      <Suspense fallback={<div>Loading...</div>}>
        <DocumentEditor />
      </Suspense>
    </div>
  );
};
```

---

## Mobile App Integration

### 1. React Native Setup
```javascript
// services/api.native.js
import axios from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';

const apiClient = axios.create({
  baseURL: 'https://api.mytypist.com',
  timeout: 30000,
});

// Token management for mobile
apiClient.interceptors.request.use(async (config) => {
  const token = await AsyncStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export default apiClient;
```

### 2. File Upload (React Native)
```javascript
// components/MobileFileUpload.jsx
import { launchImageLibrary, launchCamera } from 'react-native-image-picker';

const MobileFileUpload = () => {
  const selectFile = () => {
    const options = {
      mediaType: 'mixed',
      includeBase64: false,
      maxHeight: 2000,
      maxWidth: 2000,
    };

    launchImageLibrary(options, (response) => {
      if (response.assets) {
        uploadFile(response.assets[0]);
      }
    });
  };

  const uploadFile = async (file) => {
    const formData = new FormData();
    formData.append('file', {
      uri: file.uri,
      type: file.type,
      name: file.fileName,
    });

    try {
      const response = await apiClient.post('/api/templates/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      
      console.log('Upload successful:', response.data);
    } catch (error) {
      console.error('Upload failed:', error);
    }
  };

  return (
    <TouchableOpacity onPress={selectFile}>
      <Text>Upload File</Text>
    </TouchableOpacity>
  );
};
```

---

## Testing Integration

### 1. API Testing
```javascript
// tests/api.test.js
import { describe, it, expect, beforeEach } from 'vitest';
import apiClient from '../services/client';

describe('MyTypist API Integration', () => {
  let authToken;

  beforeEach(async () => {
    // Login for tests
    const response = await apiClient.post('/api/auth/login', {
      email: 'test@example.com',
      password: 'testpassword'
    });
    authToken = response.data.access_token;
    apiClient.defaults.headers.Authorization = `Bearer ${authToken}`;
  });

  it('should fetch templates', async () => {
    const response = await apiClient.get('/api/templates');
    expect(response.status).toBe(200);
    expect(response.data.templates).toBeInstanceOf(Array);
  });

  it('should generate document', async () => {
    const response = await apiClient.post('/api/documents/generate', {
      template_id: 1,
      placeholders: {
        customer_name: 'Test Customer',
        amount: '₦10,000'
      }
    });
    
    expect(response.status).toBe(201);
    expect(response.data.download_url).toBeDefined();
  });
});
```

---

## Environment Configuration

### Development
```javascript
// config/development.js
export default {
  API_URL: 'http://localhost:5000',
  WEBSOCKET_URL: 'ws://localhost:5000/ws',
  ENVIRONMENT: 'development',
  DEBUG: true,
  CACHE_TTL: 60000, // 1 minute
};
```

### Production
```javascript
// config/production.js
export default {
  API_URL: 'https://api.mytypist.com',
  WEBSOCKET_URL: 'wss://api.mytypist.com/ws',
  ENVIRONMENT: 'production',
  DEBUG: false,
  CACHE_TTL: 300000, // 5 minutes
};
```

---

## Security Best Practices

### 1. Token Storage
```javascript
// utils/tokenStorage.js
export const tokenStorage = {
  setTokens(accessToken, refreshToken) {
    // Use secure storage in production
    if (typeof window !== 'undefined') {
      localStorage.setItem('access_token', accessToken);
      localStorage.setItem('refresh_token', refreshToken);
    }
  },

  getAccessToken() {
    return typeof window !== 'undefined' 
      ? localStorage.getItem('access_token') 
      : null;
  },

  clearTokens() {
    if (typeof window !== 'undefined') {
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      localStorage.removeItem('user');
    }
  }
};
```

### 2. Input Validation
```javascript
// utils/validation.js
export const validateFileUpload = (file) => {
  const allowedTypes = [
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/msword',
    'application/pdf'
  ];

  const maxSize = 100 * 1024 * 1024; // 100MB

  if (!allowedTypes.includes(file.type)) {
    throw new Error('File type not supported');
  }

  if (file.size > maxSize) {
    throw new Error('File size too large');
  }

  return true;
};
```

---

## Performance Monitoring

### 1. Frontend Performance Tracking
```javascript
// utils/performance.js
export const performanceTracker = {
  startTimer(operation) {
    return performance.now();
  },

  endTimer(startTime, operation) {
    const duration = performance.now() - startTime;
    console.log(`${operation} took ${duration.toFixed(2)}ms`);
    
    // Send to analytics if needed
    if (duration > 1000) {
      this.reportSlowOperation(operation, duration);
    }
    
    return duration;
  },

  reportSlowOperation(operation, duration) {
    // Report to monitoring service
    console.warn(`Slow operation detected: ${operation} - ${duration}ms`);
  }
};
```

This comprehensive frontend integration guide ensures smooth integration with the MyTypist Backend API across all modern frontend frameworks and platforms.