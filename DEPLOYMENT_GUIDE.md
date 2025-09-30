# MyTypist Backend - Deployment Guide

**Generated**: 2025-09-26T04:40:00+01:00  
**Status**: PRODUCTION READY DEPLOYMENT GUIDE  
**All Critical Issues**: RESOLVED  

---

## 🚀 Quick Start (Development)

### Prerequisites
- Python 3.11+
- PostgreSQL 16+
- Redis 7+ (optional)
- Docker & Docker Compose (optional)

### Option 1: Docker Compose (Recommended)
```bash
# Clone and setup
git clone <repository>
cd MyTypist/backend

# Copy environment file
cp env.example .env

# Start all services
docker-compose up -d

# Run migrations
docker-compose exec app alembic upgrade head

# View logs
docker-compose logs -f app
```

### Option 2: Local Development
```bash
# Install dependencies
pip install -r requirements.txt
# OR
pip install -e .

# Setup environment
cp env.example .env
# Edit .env with your database credentials

# Setup database
createdb mytypistdb
alembic upgrade head

# Start application
python main.py
# OR
uvicorn main:app --reload
```

---

## 🏗️ Production Deployment

### 1. Environment Setup
```bash
# Production environment variables
export DEBUG=false
export JWT_SECRET_KEY="your-secure-32-character-jwt-secret-key"
export SECRET_KEY="your-secure-32-character-secret-key"
export DATABASE_URL="postgresql://user:pass@host:port/db"
export REDIS_URL="redis://user:pass@host:port"

# Optional but recommended
export SENDGRID_API_KEY="your-sendgrid-key"
export FLUTTERWAVE_PUBLIC_KEY="your-flutterwave-public-key"
export FLUTTERWAVE_SECRET_KEY="your-flutterwave-secret-key"
```

### 2. Database Setup
```bash
# Run migrations
alembic upgrade head

# Create admin user (optional)
python -c "
from app.services.auth_service import AuthService
from database import SessionLocal
db = SessionLocal()
AuthService.create_admin_user(db, 'admin@example.com', 'secure-password')
db.close()
"
```

### 3. Production Server
```bash
# Install production server
pip install gunicorn

# Start with gunicorn
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000

# OR use the provided config
gunicorn main:app -c gunicorn.conf.py
```

### 4. Nginx Configuration (Optional)
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static/ {
        alias /app/static/;
    }
}
```

---

## 🔧 Configuration Options

### Required Environment Variables
```bash
# Security (REQUIRED for production)
JWT_SECRET_KEY=your-jwt-secret-32-chars-minimum
SECRET_KEY=your-secret-32-chars-minimum

# Database (REQUIRED)
DATABASE_URL=postgresql://user:pass@host:port/db
POSTGRES_USER=mytypist
POSTGRES_PASSWORD=secure-password
POSTGRES_DB=mytypistdb

# Application
DEBUG=false  # Set to true for development
APP_NAME=MyTypist
```

### Optional Environment Variables
```bash
# Redis (Optional - graceful degradation)
REDIS_URL=redis://user:pass@host:port
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=secure-password

# File Storage
STORAGE_PATH=/app/storage
MAX_FILE_SIZE=104857600  # 100MB

# Email (Optional)
SENDGRID_API_KEY=your-sendgrid-key
SENDGRID_FROM_EMAIL=noreply@yourdomain.com

# Payment (Optional)
FLUTTERWAVE_PUBLIC_KEY=your-public-key
FLUTTERWAVE_SECRET_KEY=your-secret-key

# Performance
DB_POOL_SIZE=20
CACHE_TTL=3600
```

---

## 🏥 Health Checks & Monitoring

### Health Check Endpoint
```bash
# Check application health
curl http://localhost:8000/health

# Expected response:
{
  "status": "healthy",
  "timestamp": "2025-09-26T04:40:00Z",
  "version": "1.0.0",
  "database": "connected",
  "redis": "connected"  # or "unavailable" if optional
}
```

### Monitoring Endpoints
```bash
# Application metrics
curl http://localhost:8000/metrics

# System information
curl http://localhost:8000/api/admin/system/info
```

---

## 🔒 Security Checklist

### Production Security
- [ ] **JWT_SECRET_KEY**: Use cryptographically secure random key (32+ chars)
- [ ] **SECRET_KEY**: Use cryptographically secure random key (32+ chars)
- [ ] **Database**: Use strong passwords, enable SSL
- [ ] **Redis**: Enable authentication, use secure passwords
- [ ] **HTTPS**: Enable SSL/TLS in production
- [ ] **Firewall**: Restrict access to database and Redis ports
- [ ] **File Uploads**: Validate file types and sizes
- [ ] **Rate Limiting**: Enable rate limiting for API endpoints

### Security Headers (Nginx)
```nginx
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-XSS-Protection "1; mode=block" always;
add_header X-Content-Type-Options "nosniff" always;
add_header Referrer-Policy "no-referrer-when-downgrade" always;
add_header Content-Security-Policy "default-src 'self'" always;
```

---

## 📊 Performance Optimization

### Database Optimization
```sql
-- Create additional indexes for performance
CREATE INDEX CONCURRENTLY idx_documents_user_status ON documents(user_id, status);
CREATE INDEX CONCURRENTLY idx_templates_category_active ON templates(category, is_active);
CREATE INDEX CONCURRENTLY idx_page_visits_created_at ON page_visits(created_at);
```

### Caching Strategy
- **L1 Cache**: In-memory caching for frequently accessed data
- **L2 Cache**: Redis for shared caching across instances
- **Database**: Query result caching for expensive operations

### File Storage
```bash
# Create storage directories
mkdir -p /app/storage/{templates,documents,uploads,previews,quarantine}
chmod -R 755 /app/storage
```

---

## 🐛 Troubleshooting

### Common Issues

#### Application Won't Start
```bash
# Check environment variables
python -c "from config import settings; print('Config loaded successfully')"

# Check database connection
python -c "from database import engine; engine.connect(); print('Database connected')"

# Check imports
python -c "from main import app; print('All imports successful')"
```

#### Database Issues
```bash
# Check migration status
alembic current

# Run migrations
alembic upgrade head

# Reset database (CAUTION: DATA LOSS)
alembic downgrade base
alembic upgrade head
```

#### Redis Issues
```bash
# Test Redis connection
redis-cli ping

# Check Redis logs
docker-compose logs redis
```

### Performance Issues
```bash
# Check system resources
curl http://localhost:8000/api/admin/system/metrics

# Monitor database queries
# Enable query logging in PostgreSQL

# Check application logs
tail -f logs/app.log
```

---

## 📋 Deployment Checklist

### Pre-Deployment
- [ ] **Environment Variables**: All required variables set
- [ ] **Database**: PostgreSQL running and accessible
- [ ] **Migrations**: All database migrations applied
- [ ] **Dependencies**: All Python packages installed
- [ ] **Storage**: File storage directories created
- [ ] **Security**: Strong passwords and keys configured

### Post-Deployment
- [ ] **Health Check**: `/health` endpoint returns 200
- [ ] **Database**: Can create/read/update/delete records
- [ ] **File Upload**: Can upload and process templates
- [ ] **Authentication**: User registration and login work
- [ ] **API Docs**: `/docs` endpoint accessible
- [ ] **Monitoring**: Metrics collection working

### Production Readiness
- [ ] **SSL/TLS**: HTTPS enabled
- [ ] **Backup**: Database backup strategy implemented
- [ ] **Monitoring**: Application monitoring setup
- [ ] **Logging**: Centralized logging configured
- [ ] **Scaling**: Load balancer and multiple instances (if needed)

---

## 🎯 Success Metrics

### Application Performance
- **Startup Time**: < 10 seconds
- **Response Time**: < 500ms for API endpoints
- **Document Processing**: < 30 seconds for typical documents
- **Memory Usage**: < 512MB per instance

### System Health
- **Uptime**: 99.9% availability target
- **Error Rate**: < 1% of requests
- **Database Connections**: < 80% of pool capacity
- **Redis Memory**: < 80% of available memory

---

**Deployment Status**: ✅ READY FOR PRODUCTION  
**Last Updated**: 2025-09-26T04:40:00+01:00  
**Version**: 1.0.0  
