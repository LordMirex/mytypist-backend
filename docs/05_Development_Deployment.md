# MyTypist Production Deployment Guide

## Overview

This guide covers deploying MyTypist Backend to production with optimal performance, security, and reliability. The system is designed to handle high-volume document generation with sub-500ms response times.

## Prerequisites

### System Requirements
- **CPU**: Minimum 2 cores, recommended 4+ cores
- **RAM**: Minimum 4GB, recommended 8GB+
- **Storage**: Minimum 20GB SSD
- **OS**: Ubuntu 20.04+ or similar Linux distribution

### Required Services
- **PostgreSQL 13+**: Primary database
- **Redis 6+**: Caching and task queue
- **Nginx**: Reverse proxy and load balancer
- **SSL Certificate**: Let's Encrypt or commercial certificate

---

## Environment Setup

### 1. System Dependencies
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python 3.11
sudo apt install python3.11 python3.11-venv python3.11-dev

# Install PostgreSQL
sudo apt install postgresql postgresql-contrib

# Install Redis
sudo apt install redis-server

# Install Nginx
sudo apt install nginx

# Install system dependencies
sudo apt install build-essential libpq-dev python3-magic
```

### 2. Application Setup
```bash
# Clone repository
git clone <your-repository-url>
cd mytypist-backend

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies (pyproject.toml)
pip install -e .  # or: pip install .

# Or use uv for faster installation
pip install uv
uv sync
```

### 3. Environment Configuration
Create a production `.env` file:

```env
# Environment
ENVIRONMENT=production
DEBUG=False

# Database (PostgreSQL)
DATABASE_URL=postgresql://mytypist_user:secure_password@localhost:5432/mytypist_db

# Redis
REDIS_URL=redis://localhost:6379/0

# Security
SECRET_KEY=your-super-secure-secret-key-minimum-32-characters
ENCRYPTION_KEY=your-256-bit-encryption-key-for-file-encryption

# JWT Settings
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=30

# File Storage
STORAGE_PATH=/var/mytypist/storage
MAX_FILE_SIZE=104857600  # 100MB
ENCRYPTION_ENABLED=true

# Payment Integration
FLUTTERWAVE_SECRET_KEY=your-flutterwave-secret-key
FLUTTERWAVE_PUBLIC_KEY=your-flutterwave-public-key
FLUTTERWAVE_WEBHOOK_SECRET=your-webhook-secret

# Email Configuration
SENDGRID_API_KEY=your-sendgrid-api-key
FROM_EMAIL=noreply@mytypist.com

# Performance
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=30
WORKERS=4

# Monitoring
SENTRY_DSN=your-sentry-dsn-for-error-tracking
```

---

## Database Setup

### 1. PostgreSQL Configuration
```bash
# Switch to postgres user
sudo -u postgres psql

# Create database and user
CREATE DATABASE mytypist_db;
CREATE USER mytypist_user WITH PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE mytypist_db TO mytypist_user;
ALTER USER mytypist_user CREATEDB;
\q
```

### 2. Production PostgreSQL Optimization
Edit `/etc/postgresql/13/main/postgresql.conf`:

```conf
# Memory settings
shared_buffers = 256MB
effective_cache_size = 1GB
work_mem = 4MB
maintenance_work_mem = 64MB

# Connection settings
max_connections = 200
superuser_reserved_connections = 3

# Performance settings
wal_level = replica
checkpoint_completion_target = 0.9
random_page_cost = 1.1
effective_io_concurrency = 200

# Logging
log_min_duration_statement = 1000  # Log slow queries
log_line_prefix = '%t [%p]: [%l-1] user=%u,db=%d,app=%a,client=%h '
```

### 3. Database Migration
```bash
# METHOD 1: Use Alembic migrations (Recommended)
alembic upgrade head

# METHOD 2: For fresh deployments or if migrations fail
# All essential tables are created automatically on first run
python main.py  # Tables auto-created on startup

# Verify all tables exist
psql $DATABASE_URL -c "\dt"
# Should show: users, templates, documents, placeholders, signatures, payments, subscriptions, audit_logs, etc.

# Create initial admin user (optional)
python scripts/create_admin.py
```

---

## Application Deployment

### 1. Gunicorn Configuration
The application includes optimized `gunicorn.conf.py` for production:

```bash
# Start with Gunicorn
gunicorn main:app -c gunicorn.conf.py

# Or use systemd service (recommended)
sudo systemctl start mytypist-backend
sudo systemctl enable mytypist-backend
```

### 2. Systemd Service
Create `/etc/systemd/system/mytypist-backend.service`:

```ini
[Unit]
Description=MyTypist Backend API
After=network.target postgresql.service redis.service

[Service]
Type=forking
User=mytypist
Group=mytypist
WorkingDirectory=/var/www/mytypist-backend
Environment=PATH=/var/www/mytypist-backend/venv/bin
ExecStart=/var/www/mytypist-backend/venv/bin/gunicorn main:app -c gunicorn.conf.py
ExecReload=/bin/kill -s HUP $MAINPID
KillMode=mixed
TimeoutStopSec=5
PrivateTmp=true
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 3. Nginx Configuration
Create `/etc/nginx/sites-available/mytypist`:

```nginx
upstream mytypist_backend {
    least_conn;
    server 127.0.0.1:5000 max_fails=3 fail_timeout=30s;
    keepalive 32;
}

# Rate limiting
limit_req_zone $binary_remote_addr zone=api:10m rate=100r/s;
limit_req_zone $binary_remote_addr zone=auth:10m rate=5r/s;
limit_req_zone $binary_remote_addr zone=upload:10m rate=10r/s;

server {
    listen 443 ssl http2;
    server_name api.mytypist.com;

    # SSL Configuration
    ssl_certificate /etc/letsencrypt/live/api.mytypist.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.mytypist.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512;
    ssl_prefer_server_ciphers off;

    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains";

    # File upload size limit
    client_max_body_size 100M;

    # API endpoints with rate limiting
    location /api/auth/ {
        limit_req zone=auth burst=10 nodelay;
        proxy_pass http://mytypist_backend;
        include /etc/nginx/proxy_params;
    }

    location /api/documents/upload {
        limit_req zone=upload burst=5 nodelay;
        proxy_pass http://mytypist_backend;
        include /etc/nginx/proxy_params;
        proxy_read_timeout 300;
    }

    location /api/ {
        limit_req zone=api burst=20 nodelay;
        proxy_pass http://mytypist_backend;
        include /etc/nginx/proxy_params;
    }

    # Health check endpoint (no rate limiting)
    location /health {
        proxy_pass http://mytypist_backend;
        include /etc/nginx/proxy_params;
    }

    # Static files (if serving any)
    location /static/ {
        alias /var/www/mytypist-backend/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}

# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name api.mytypist.com;
    return 301 https://$server_name$request_uri;
}
```

### 4. Proxy Parameters
Create `/etc/nginx/proxy_params`:

```nginx
proxy_set_header Host $http_host;
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
proxy_set_header X-Forwarded-Host $host;
proxy_set_header X-Forwarded-Port $server_port;

proxy_connect_timeout 60s;
proxy_send_timeout 60s;
proxy_read_timeout 60s;

proxy_buffering on;
proxy_buffer_size 8k;
proxy_buffers 16 8k;
proxy_busy_buffers_size 16k;

proxy_http_version 1.1;
proxy_set_header Connection "";
```

---

## SSL/TLS Setup

### 1. Let's Encrypt Certificate
```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d api.mytypist.com

# Auto-renewal
sudo crontab -e
# Add: 0 12 * * * /usr/bin/certbot renew --quiet
```

### 2. SSL Security Test
Test your SSL configuration at: https://www.ssllabs.com/ssltest/

---

## Performance Optimization

### 1. System Optimization
```bash
# Increase file descriptor limits
echo "* soft nofile 65536" >> /etc/security/limits.conf
echo "* hard nofile 65536" >> /etc/security/limits.conf

# Optimize kernel parameters
echo "net.core.somaxconn = 1024" >> /etc/sysctl.conf
echo "net.ipv4.tcp_keepalive_time = 600" >> /etc/sysctl.conf
sudo sysctl -p
```

### 2. PostgreSQL Tuning
```bash
# Use PGTune for automatic configuration
# Visit: https://pgtune.leopard.in.ua/
# Input your system specs and copy the generated configuration
```

### 3. Redis Optimization
Edit `/etc/redis/redis.conf`:

```conf
# Memory optimization
maxmemory 1gb
maxmemory-policy allkeys-lru

# Performance
tcp-keepalive 300
timeout 300

# Persistence (adjust based on needs)
save 900 1
save 300 10
save 60 10000
```

---

## Monitoring and Alerting

### 1. Built-in Monitoring
Access monitoring dashboard at:
- Health: `https://api.mytypist.com/health`
- Detailed health: `https://api.mytypist.com/api/monitoring/health/detailed`
- Performance stats: `https://api.mytypist.com/api/monitoring/performance/stats`

### 2. Log Management
```bash
# Application logs
tail -f /var/log/mytypist/app.log

# Nginx logs
tail -f /var/log/nginx/access.log
tail -f /var/log/nginx/error.log

# System logs
journalctl -u mytypist-backend -f
```

### 3. Automated Health Checks
Set up external monitoring (Uptime Robot, Pingdom, etc.) for:
- `/health` endpoint every 1 minute
- `/api/monitoring/health/detailed` every 5 minutes

---

## Backup and Recovery

### 1. Database Backup
```bash
# Daily backup script
#!/bin/bash
BACKUP_DIR="/var/backups/mytypist"
DATE=$(date +%Y%m%d_%H%M%S)

pg_dump mytypist_db | gzip > "$BACKUP_DIR/mytypist_db_$DATE.sql.gz"

# Keep only last 30 days
find $BACKUP_DIR -name "*.sql.gz" -mtime +30 -delete
```

### 2. File Storage Backup
```bash
# Backup uploaded files
rsync -av /var/mytypist/storage/ /backup/mytypist/storage/
```

### 3. Recovery Procedures
```bash
# Restore database
gunzip < mytypist_db_20250115_120000.sql.gz | psql mytypist_db

# Restore files
rsync -av /backup/mytypist/storage/ /var/mytypist/storage/
```

---

## Security Checklist

### Pre-Deployment Security
- [ ] All secrets in environment variables (not in code)
- [ ] SSL certificate installed and configured
- [ ] Database credentials secured
- [ ] File upload validation enabled
- [ ] Rate limiting configured
- [ ] Security headers enabled
- [ ] Firewall configured
- [ ] Regular security updates scheduled

### Production Security Hardening
```bash
# Firewall setup
sudo ufw enable
sudo ufw allow 22    # SSH
sudo ufw allow 80    # HTTP
sudo ufw allow 443   # HTTPS

# Fail2ban for intrusion prevention
sudo apt install fail2ban
sudo systemctl enable fail2ban
```

---

## Performance Benchmarks

### Expected Performance Metrics
- **API Response Time**: < 100ms (simple endpoints)
- **Document Generation**: < 500ms (5 documents)
- **Concurrent Users**: 1000+ simultaneous
- **Database Queries**: < 50ms average
- **Cache Operations**: < 5ms average
- **Memory Usage**: < 2GB under normal load

### Load Testing
```bash
# Install k6 for load testing
sudo apt install k6

# Run load test
k6 run scripts/load_test.js
```

---

## Scaling Options

### Horizontal Scaling
1. **Load Balancer**: Multiple application instances behind Nginx
2. **Database Read Replicas**: PostgreSQL read-only replicas
3. **Redis Cluster**: Redis clustering for high availability
4. **CDN**: CloudFlare or AWS CloudFront for static assets

### Vertical Scaling
1. **CPU**: Increase worker processes
2. **Memory**: Optimize caching and connection pools
3. **Storage**: SSD for better I/O performance

---

## Troubleshooting

### Common Issues

#### High Memory Usage
```bash
# Check memory consumers
ps aux --sort=-%mem | head -10

# Optimize garbage collection
export PYTHONMALLOC=malloc
```

#### Database Connection Issues
```bash
# Check PostgreSQL connections
sudo -u postgres psql -c "SELECT count(*) FROM pg_stat_activity;"

# Monitor connection pool
curl https://api.mytypist.com/api/monitoring/performance/stats
```

#### Slow Response Times
```bash
# Check application logs
tail -f /var/log/mytypist/app.log | grep "SLOW_REQUEST"

# Monitor Nginx access logs
tail -f /var/log/nginx/access.log | awk '$NF > 1.0'
```

### Performance Debugging
```bash
# Application profiling
python -m cProfile -o profile.stats main.py

# Database query analysis
sudo -u postgres psql mytypist_db -c "SELECT query, calls, total_time, mean_time FROM pg_stat_statements ORDER BY total_time DESC LIMIT 10;"
```

---

## Deployment Checklist

### Pre-Deployment
- [ ] Environment variables configured
- [ ] Database migrated
- [ ] SSL certificate installed
- [ ] Load testing completed
- [ ] Security scan passed
- [ ] Backup strategy implemented

### Post-Deployment
- [ ] Health checks passing
- [ ] Monitoring alerts configured
- [ ] Error tracking enabled
- [ ] Performance metrics normal
- [ ] Documentation updated
- [ ] Team notified

### Regular Maintenance
- [ ] Weekly security updates
- [ ] Monthly performance reviews
- [ ] Quarterly dependency updates
- [ ] Backup restoration tests
- [ ] SSL certificate renewal (automated)

---

## Support and Maintenance

### Log Locations
- **Application**: `/var/log/mytypist/`
- **Nginx**: `/var/log/nginx/`
- **PostgreSQL**: `/var/log/postgresql/`
- **Redis**: `/var/log/redis/`

### Health Check Commands
```bash
# Application health
curl https://api.mytypist.com/health

# Database health
sudo -u postgres pg_isready

# Redis health
redis-cli ping

# Service status
systemctl status mytypist-backend
systemctl status postgresql
systemctl status redis
systemctl status nginx
```

## 📋 **DEPLOYMENT CHECKLIST**

### 🔧 **Pre-Deployment Setup**

#### 1. **Environment Variables** (CRITICAL)
```bash
# Generate strong secrets (minimum 32 characters)
SECRET_KEY="your-cryptographically-secure-secret-key-32-chars-minimum"
JWT_SECRET_KEY="different-jwt-secret-key-32-chars-minimum"

# Database (Use PostgreSQL in production)
DATABASE_URL="postgresql://user:password@host:port/database"

# Redis (Required for security features)
REDIS_URL="redis://user:password@host:port/database"
REDIS_ENABLED="true"

# Security Settings
DEBUG="false"
ENVIRONMENT="production"

# CORS Settings (Restrict to your domains)
ALLOWED_ORIGINS='["https://mytypist.net"]'
ALLOWED_HOSTS='["mytypist.net", "api.mytypist.net"]'
```

#### 2. **Database Migration**
```bash
# Install dependencies (use uv for faster installation)
pip install uv
uv sync

# Run database migrations
alembic upgrade head

# Alternative: Start app to auto-create tables
python main.py

# Verify database setup
curl http://localhost:5000/health
# Should return: {"status": "healthy", "services": {"database": "healthy", "redis": "healthy"}}


#### 3. **SSL/TLS Configuration** (CRITICAL)
```nginx
# Nginx configuration example
server {
    listen 443 ssl http2;
    server_name mytypist.net;

    ssl_certificate /path/to/certificate.pem;
    ssl_certificate_key /path/to/private.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 🔍 **Security Testing**
#### 1. **Security Headers Verification**
```bash
curl -I https://mytypist.net/
# Verify presence of:
# - X-Content-Type-Options: nosniff
# - X-Frame-Options: DENY
# - X-XSS-Protection: 1; mode=block
# - Strict-Transport-Security: max-age=31536000
# - Content-Security-Policy: default-src 'self'
```

#### 3. **Rate Limiting Testing**
```bash
# Test rate limiting (should return 429 after limits exceeded)
for i in {1..100}; do
  curl -X POST "https://mytypist.net/api/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"email":"test@example.com","password":"wrongpass"}'
done
```

### 🔐 **Security Configuration**

#### 1. **Firewall Rules**
```bash
# Allow only necessary ports
ufw allow 22/tcp    # SSH
ufw allow 80/tcp    # HTTP (redirect to HTTPS)
ufw allow 443/tcp   # HTTPS
ufw deny 5000/tcp   # Block direct access to app
ufw enable
```

#### 2. **Monitoring Setup**
```bash
# Set up log monitoring
tail -f /var/log/mytypist/security.log | grep "SECURITY_ALERT"



#### 3. **Backup Configuration**
```bash
# Automated database backups
crontab -e
# Add: 0 2 * * * /usr/local/bin/backup-mytypist-db.sh

# Backup script example
#!/bin/bash
pg_dump $DATABASE_URL > /backups/mytypist-$(date +%Y%m%d).sql
find /backups -name "mytypist-*.sql" -mtime +30 -delete
```

### 📊 **Monitoring & Alerting**

#### 1. **Security Metrics Dashboard**
#### 2. **Health Checks**
```bash
# Application health
curl https://![alt text](image.png)/health


#### 3. **Log Analysis**
```bash
# Security incident analysis
grep "SECURITY_ALERT" /var/log/mytypist/security.log | tail -20

# Brute force detection
grep "BRUTE_FORCE_ATTACK" /var/log/mytypist/security.log

```

## ⚠️ **CRITICAL SECURITY WARNINGS**

### 1. **IMMEDIATE ACTIONS REQUIRED**
- [ ] Change default SECRET_KEY and JWT_SECRET_KEY
- [ ] Enable HTTPS with valid SSL certificate
- [ ] Configure Redis for session and rate limiting
- [ ] Set up database backups
- [ ] Configure firewall rules
- [ ] Set DEBUG=false in production

### 2. **ONGOING SECURITY MAINTENANCE**
- [ ] Regular security updates
- [ ] Monitor security logs daily
- [ ] Review user permissions quarterly
- [ ] Update threat indicators monthly
- [ ] Test backup/recovery procedures
- [ ] Security audit annually

### 3. **COMPLIANCE CONSIDERATIONS**
- **GDPR**: Data export/deletion endpoints implemented
- **SOC2**: Audit logging and access controls ready
- **ISO 27001**: Security monitoring and incident response
- **PCI DSS**: Payment processing security (if applicable)

## 🛠️ **TROUBLESHOOTING**

```

## 📞 **SECURITY CONTACT**

For security issues or questions:
- Create a GitHub issue with [SECURITY] tag
- Email: security@mytypist.com
- Emergency: Follow incident response procedures

---
**Your MyTypist backend is now production-ready with enterprise-grade security! 🚀**

### Emergency Procedures
1. **High Load**: Scale horizontally or increase resources
2. **Database Issues**: Check connections and run VACUUM ANALYZE
3. **Memory Leaks**: Restart application services
4. **Security Incidents**: Review audit logs and block malicious IPs

This deployment guide ensures MyTypist Backend runs optimally in production with enterprise-grade performance and security.