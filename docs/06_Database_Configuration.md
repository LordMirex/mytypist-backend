# Database Configuration Guide

## Overview

MyTypist Backend uses PostgreSQL (development and production) with advanced optimization configurations for maximum performance. This guide covers database setup, optimization, migration, and maintenance.

## Database Architecture

### Schema Overview
```sql
-- Core Tables
users                 -- User accounts and authentication
templates            -- Document templates with placeholders
documents            -- Generated documents and metadata
signatures           -- Digital signatures and certificates
payments             -- Payment transactions and billing
audit_logs           -- Comprehensive audit trail
visits               -- Analytics and user tracking

-- Relationships
templates(user_id) -> users(id)
documents(template_id) -> templates(id)
documents(user_id) -> users(id)
signatures(user_id) -> users(id)
payments(user_id) -> users(id)
audit_logs(user_id) -> users(id)
```

---

        cursor.execute("PRAGMA foreign_keys=ON")
        
        # Optimize synchronous mode
        cursor.execute("PRAGMA synchronous=NORMAL")
        
        # Set busy timeout (30 seconds)
        cursor.execute("PRAGMA busy_timeout=30000")
        
        # Memory-mapped I/O
        cursor.execute("PRAGMA mmap_size=268435456")  # 256MB
        
        # Optimize temp storage
        cursor.execute("PRAGMA temp_store=MEMORY")
        
        cursor.close()
```

### 2. SQLite Performance Monitoring
```sql
-- Check SQLite performance stats
PRAGMA compile_options;
PRAGMA journal_mode;
PRAGMA cache_size;
PRAGMA synchronous;
PRAGMA temp_store;

-- Analyze database
ANALYZE;

-- Check table statistics
SELECT name, rootpage, ncols, nentry FROM sqlite_stat1;
```

---

## PostgreSQL Configuration (Production)

### 1. Database Installation and Setup
```bash
# Install PostgreSQL 15
sudo apt update
sudo apt install postgresql-15 postgresql-client-15 postgresql-contrib-15

# Create database and user
sudo -u postgres psql << EOF
CREATE DATABASE mytypist_prod;
CREATE USER mytypist_user WITH PASSWORD 'secure_production_password';
GRANT ALL PRIVILEGES ON DATABASE mytypist_prod TO mytypist_user;
ALTER USER mytypist_user CREATEDB;
ALTER DATABASE mytypist_prod OWNER TO mytypist_user;
EOF
```

### 2. Production PostgreSQL Configuration
Edit `/etc/postgresql/15/main/postgresql.conf`:

```conf
# Connection Settings
listen_addresses = 'localhost'
port = 5432
max_connections = 200
superuser_reserved_connections = 3

# Memory Settings (adjust based on available RAM)
shared_buffers = 256MB          # 25% of RAM
effective_cache_size = 1GB      # 75% of RAM  
work_mem = 4MB                  # RAM / max_connections
maintenance_work_mem = 64MB     # RAM / 16

# Checkpoint Settings
wal_level = replica
wal_buffers = 16MB
checkpoint_completion_target = 0.9
checkpoint_timeout = 10min
max_wal_size = 1GB
min_wal_size = 80MB

# Query Planning
random_page_cost = 1.1          # SSD optimization
effective_io_concurrency = 200  # Number of concurrent I/O operations

# Logging and Monitoring
log_destination = 'csvlog'
logging_collector = on
log_directory = 'log'
log_filename = 'postgresql-%Y-%m-%d_%H%M%S.log'
log_min_duration_statement = 1000  # Log queries > 1 second
log_line_prefix = '%t [%p]: [%l-1] user=%u,db=%d,app=%a,client=%h '
log_lock_waits = on
log_temp_files = 10MB

# Statistics
track_activities = on
track_counts = on
track_io_timing = on
track_functions = pl
```

### 3. PostgreSQL Performance Tuning
```sql
-- Install pg_stat_statements extension
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- Monitor slow queries
SELECT query, calls, total_time, mean_time, rows
FROM pg_stat_statements 
WHERE mean_time > 100  -- Queries averaging > 100ms
ORDER BY total_time DESC 
LIMIT 10;

-- Check index usage
SELECT schemaname, tablename, attname, n_distinct, correlation
FROM pg_stats
WHERE tablename IN ('users', 'documents', 'templates', 'payments')
ORDER BY tablename, attname;

-- Monitor connection usage
SELECT state, count(*) 
FROM pg_stat_activity 
GROUP BY state;

-- Check database size and growth
SELECT pg_database.datname,
       pg_size_pretty(pg_database_size(pg_database.datname)) AS size
FROM pg_database
WHERE pg_database.datname = 'mytypist_prod';
```

---

## Database Optimization

### 1. Index Strategy
```sql
-- Primary indexes for performance
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_active ON users(is_active);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_documents_user_id ON documents(user_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_documents_created_at ON documents(created_at);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_documents_status ON documents(status);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_templates_public ON templates(is_public);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_templates_category ON templates(category);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_payments_user_id ON payments(user_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_payments_status ON payments(status);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_payments_created_at ON payments(created_at);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_audit_logs_event_type ON audit_logs(event_type);

-- Composite indexes for common queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_documents_user_status 
ON documents(user_id, status);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_payments_user_status_date 
ON payments(user_id, status, created_at);
```

### 2. Query Optimization
```sql
-- Optimize frequently used queries
-- User dashboard query
EXPLAIN ANALYZE 
SELECT d.*, t.name as template_name
FROM documents d
JOIN templates t ON d.template_id = t.id
WHERE d.user_id = $1 
  AND d.status = 'completed'
ORDER BY d.created_at DESC
LIMIT 20;

-- Payment history query
EXPLAIN ANALYZE
SELECT p.*, u.email
FROM payments p
JOIN users u ON p.user_id = u.id
WHERE p.status = 'completed'
  AND p.created_at >= NOW() - INTERVAL '30 days'
ORDER BY p.created_at DESC;

-- Template search query
EXPLAIN ANALYZE
SELECT t.*, u.full_name as creator_name
FROM templates t
LEFT JOIN users u ON t.user_id = u.id
WHERE t.is_public = true
  AND (t.name ILIKE '%invoice%' OR t.description ILIKE '%invoice%')
ORDER BY t.download_count DESC;
```

### 3. Database Maintenance Scripts
```sql
-- Regular maintenance procedure
DO $$
BEGIN
    -- Update table statistics
    ANALYZE;
    
    -- Reindex if needed (run during maintenance window)
    -- REINDEX DATABASE mytypist_prod;
    
    -- Clean up old audit logs (keep 90 days)
    DELETE FROM audit_logs 
    WHERE created_at < NOW() - INTERVAL '90 days';
    
    -- Clean up expired documents
    DELETE FROM documents 
    WHERE status = 'temporary' 
      AND created_at < NOW() - INTERVAL '24 hours';
    
    -- Vacuum analyze for space reclamation
    VACUUM ANALYZE;
    
    RAISE NOTICE 'Database maintenance completed successfully';
END $$;
```

---

## Connection Pooling

### 1. SQLAlchemy Pool Configuration
```python
# Production connection pool settings
def create_optimized_engine(database_url: str, environment: str):
    """Create optimized database engine based on environment"""
    
    if environment == "production":
        return create_engine(
            database_url,
            pool_size=25,                # Base connections
            max_overflow=35,             # Burst capacity
            pool_timeout=30,             # Wait time for connection
            pool_recycle=3600,           # Recycle after 1 hour
            pool_pre_ping=True,          # Validate before use
            connect_args={
                "connect_timeout": 10,
                "options": "-c statement_timeout=30000 -c idle_in_transaction_session_timeout=60000"
            }
        )
    elif environment == "staging":
        return create_engine(
            database_url,
            pool_size=10,
            max_overflow=15,
            pool_timeout=20,
            pool_recycle=1800,
            pool_pre_ping=True
        )
    else:  # development
        return create_engine(
            database_url,
            pool_size=5,
            max_overflow=10,
            pool_timeout=15,
            pool_recycle=300,
            echo=True  # SQL logging
        )
```

### 2. Connection Pool Monitoring
```python
def monitor_connection_pool():
    """Monitor database connection pool health"""
    pool = engine.pool
    
    metrics = {
        "pool_size": pool.size(),
        "checked_out": pool.checkedout(),
        "overflow": pool.overflow(),
        "checked_in": pool.checkedin(),
        "utilization_percent": (pool.checkedout() / (pool.size() + pool.overflow())) * 100
    }
    
    # Alert if utilization is high
    if metrics["utilization_percent"] > 85:
        logger.warning(f"High database pool utilization: {metrics['utilization_percent']:.1f}%")
    
    return metrics
```

---

## Database Migration

### 1. Alembic Configuration
```python
# alembic/env.py
from alembic import context
from sqlalchemy import engine_from_config, pool
from logging.config import fileConfig

from database import Base
from config import settings

# Alembic Config object
config = context.config

# Set database URL
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Configure logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

def run_migrations_offline():
    """Run migrations in 'offline' mode"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    """Run migrations in 'online' mode"""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, 
            target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

### 2. Migration Best Practices
```bash
# Create new migration
alembic revision --autogenerate -m "Add user preferences table"

# Review migration before applying
alembic show head

# Apply migration
alembic upgrade head

# Rollback if needed
alembic downgrade -1

# Check current revision
alembic current

# Show migration history
alembic history --verbose
```

---

## Data Seeding

### 1. Sample Data Creation
```python
# scripts/seed_database.py
from database import SessionLocal
from app.models.user import User, UserRole
from app.models.template import Template
from app.services.auth_service import AuthService

def create_sample_users(db):
    """Create sample users for testing"""
    users = [
        {
            "email": "admin@mytypist.com",
            "full_name": "System Administrator",
            "role": UserRole.ADMIN,
            "password": "admin123"
        },
        {
            "email": "user@example.com", 
            "full_name": "John Doe",
            "company_name": "Acme Corp",
            "role": UserRole.USER,
            "password": "user123"
        }
    ]
    
    for user_data in users:
        # Check if user exists
        existing = db.query(User).filter(User.email == user_data["email"]).first()
        if existing:
            continue
        
        # Create new user
        password = user_data.pop("password")
        user = User(**user_data)
        user.hashed_password = AuthService.hash_password(password)
        user.is_active = True
        user.email_verified = True
        
        db.add(user)
    
    db.commit()

def create_sample_templates(db):
    """Create sample document templates"""
    templates = [
        {
            "name": "Invoice Template",
            "description": "Standard invoice template for Nigerian businesses",
            "category": "invoice",
            "is_public": True,
            "file_path": "templates/invoice_template.docx",
            "placeholders": [
                {"name": "company_name", "type": "text", "required": True},
                {"name": "customer_name", "type": "text", "required": True},
                {"name": "invoice_number", "type": "text", "required": True},
                {"name": "date", "type": "date", "required": True},
                {"name": "amount", "type": "currency", "required": True}
            ]
        },
        {
            "name": "Contract Template",
            "description": "Service contract template",
            "category": "contract",
            "is_public": True,
            "file_path": "templates/contract_template.docx",
            "placeholders": [
                {"name": "client_name", "type": "text", "required": True},
                {"name": "service_description", "type": "text", "required": True},
                {"name": "start_date", "type": "date", "required": True},
                {"name": "end_date", "type": "date", "required": True},
                {"name": "payment_terms", "type": "text", "required": True}
            ]
        }
    ]
    
    for template_data in templates:
        # Check if template exists
        existing = db.query(Template).filter(Template.name == template_data["name"]).first()
        if existing:
            continue
        
        template = Template(**template_data)
        db.add(template)
    
    db.commit()

def main():
    """Seed database with sample data"""
    db = SessionLocal()
    
    try:
        print("🌱 Seeding database with sample data...")
        
        create_sample_users(db)
        print("✅ Sample users created")
        
        create_sample_templates(db)
        print("✅ Sample templates created")
        
        print("✅ Database seeding completed")
    except Exception as e:
        print(f"❌ Database seeding failed: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    main()
```

---

## Backup and Recovery

### 1. Automated Backup Script
```bash
#!/bin/bash
# scripts/backup_database.sh

# Configuration
DB_NAME="mytypist_prod"
DB_USER="mytypist_user"
BACKUP_DIR="/var/backups/mytypist"
RETENTION_DAYS=30
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Create backup directory
mkdir -p $BACKUP_DIR

# Backup database
echo "📦 Creating database backup..."
pg_dump -h localhost -U $DB_USER -d $DB_NAME | gzip > "$BACKUP_DIR/mytypist_${TIMESTAMP}.sql.gz"

# Verify backup
if [ $? -eq 0 ]; then
    echo "✅ Database backup created: mytypist_${TIMESTAMP}.sql.gz"
    
    # Get backup size
    SIZE=$(du -h "$BACKUP_DIR/mytypist_${TIMESTAMP}.sql.gz" | cut -f1)
    echo "📊 Backup size: $SIZE"
else
    echo "❌ Database backup failed"
    exit 1
fi

# Clean old backups
find $BACKUP_DIR -name "mytypist_*.sql.gz" -mtime +$RETENTION_DAYS -delete
echo "🧹 Cleaned backups older than $RETENTION_DAYS days"

# Backup file storage
echo "📁 Backing up file storage..."
rsync -av /var/mytypist/storage/ "$BACKUP_DIR/storage_${TIMESTAMP}/"

# Log backup completion
echo "$(date): Backup completed successfully" >> /var/log/mytypist/backup.log
```

### 2. Recovery Procedures
```bash
#!/bin/bash
# scripts/restore_database.sh

BACKUP_FILE=$1
DB_NAME="mytypist_prod"
DB_USER="mytypist_user"

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: $0 <backup_file.sql.gz>"
    exit 1
fi

echo "⚠️ This will replace the current database!"
read -p "Are you sure? (yes/no): " confirmation

if [ "$confirmation" != "yes" ]; then
    echo "❌ Recovery cancelled"
    exit 1
fi

# Stop application
echo "🛑 Stopping application..."
sudo systemctl stop mytypist-backend

# Drop and recreate database
echo "🗄️ Recreating database..."
sudo -u postgres psql << EOF
DROP DATABASE IF EXISTS ${DB_NAME}_temp;
CREATE DATABASE ${DB_NAME}_temp OWNER $DB_USER;
EOF

# Restore backup
echo "📥 Restoring backup..."
gunzip < $BACKUP_FILE | sudo -u postgres psql -d ${DB_NAME}_temp

# Swap databases
sudo -u postgres psql << EOF
ALTER DATABASE $DB_NAME RENAME TO ${DB_NAME}_old;
ALTER DATABASE ${DB_NAME}_temp RENAME TO $DB_NAME;
EOF

# Start application
echo "🚀 Starting application..."
sudo systemctl start mytypist-backend

# Verify restoration
sleep 10
curl -f http://localhost:5000/health

if [ $? -eq 0 ]; then
    echo "✅ Database restoration successful"
    
    # Clean up old database
    sudo -u postgres psql -c "DROP DATABASE ${DB_NAME}_old;"
else
    echo "❌ Database restoration failed"
    
    # Rollback
    sudo systemctl stop mytypist-backend
    sudo -u postgres psql << EOF
    ALTER DATABASE $DB_NAME RENAME TO ${DB_NAME}_failed;
    ALTER DATABASE ${DB_NAME}_old RENAME TO $DB_NAME;
EOF
    sudo systemctl start mytypist-backend
fi
```

---

## Database Security

### 1. Security Configuration
```sql
-- Create read-only user for reporting
CREATE USER mytypist_readonly WITH PASSWORD 'readonly_password';
GRANT CONNECT ON DATABASE mytypist_prod TO mytypist_readonly;
GRANT USAGE ON SCHEMA public TO mytypist_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO mytypist_readonly;

-- Create backup user
CREATE USER mytypist_backup WITH PASSWORD 'backup_password';
GRANT CONNECT ON DATABASE mytypist_prod TO mytypist_backup;
GRANT USAGE ON SCHEMA public TO mytypist_backup;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO mytypist_backup;

-- Row Level Security (if needed)
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;
CREATE POLICY audit_logs_policy ON audit_logs
FOR ALL TO mytypist_user
USING (true);  -- Allow all operations for main user
```

### 2. Encryption at Rest
```bash
# PostgreSQL encryption setup
# Edit postgresql.conf
ssl = on
ssl_cert_file = '/etc/ssl/certs/server.crt'
ssl_key_file = '/etc/ssl/private/server.key'
ssl_ca_file = '/etc/ssl/certs/ca.crt'

# Transparent Data Encryption (if supported)
# This requires PostgreSQL compiled with encryption support
```

---

## Performance Monitoring

### 1. Database Performance Queries
```sql
-- Monitor active connections
SELECT pid, usename, application_name, client_addr, state, query_start, query
FROM pg_stat_activity
WHERE state = 'active'
ORDER BY query_start;

-- Check table sizes
SELECT schemaname, tablename,
       pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Monitor index usage
SELECT schemaname, tablename, indexname, idx_scan, idx_tup_read, idx_tup_fetch
FROM pg_stat_user_indexes
ORDER BY idx_scan DESC;

-- Check for unused indexes
SELECT schemaname, tablename, indexname, idx_scan
FROM pg_stat_user_indexes
WHERE idx_scan = 0
  AND indexname NOT LIKE '%_pkey'  -- Exclude primary keys
ORDER BY schemaname, tablename;

-- Lock monitoring
SELECT blocked_locks.pid AS blocked_pid,
       blocked_activity.usename AS blocked_user,
       blocking_locks.pid AS blocking_pid,
       blocking_activity.usename AS blocking_user,
       blocked_activity.query AS blocked_statement,
       blocking_activity.query AS current_statement_in_blocking_process
FROM pg_catalog.pg_locks blocked_locks
JOIN pg_catalog.pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
JOIN pg_catalog.pg_locks blocking_locks ON (blocked_locks.locktype = blocking_locks.locktype
    AND blocked_locks.DATABASE IS NOT DISTINCT FROM blocking_locks.DATABASE
    AND blocked_locks.relation IS NOT DISTINCT FROM blocking_locks.relation
    AND blocked_locks.page IS NOT DISTINCT FROM blocking_locks.page
    AND blocked_locks.tuple IS NOT DISTINCT FROM blocking_locks.tuple
    AND blocked_locks.virtualxid IS NOT DISTINCT FROM blocking_locks.virtualxid
    AND blocked_locks.transactionid IS NOT DISTINCT FROM blocking_locks.transactionid
    AND blocked_locks.classid IS NOT DISTINCT FROM blocking_locks.classid
    AND blocked_locks.objid IS NOT DISTINCT FROM blocking_locks.objid
    AND blocked_locks.objsubid IS NOT DISTINCT FROM blocking_locks.objsubid
    AND blocked_locks.pid != blocking_locks.pid)
JOIN pg_catalog.pg_stat_activity blocking_activity ON blocking_activity.pid = blocking_locks.pid
WHERE NOT blocked_locks.GRANTED;
```

### 2. Automated Performance Reports
```python
# scripts/generate_db_report.py
import psycopg2
import json
from datetime import datetime, timedelta

def generate_performance_report():
    """Generate comprehensive database performance report"""
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cur = conn.cursor()
    
    report = {
        "timestamp": datetime.utcnow().isoformat(),
        "database_size": {},
        "table_stats": {},
        "slow_queries": {},
        "index_usage": {}
    }
    
    # Database size
    cur.execute("""
        SELECT pg_size_pretty(pg_database_size('mytypist_prod')) as size,
               pg_database_size('mytypist_prod') as size_bytes
    """)
    size_data = cur.fetchone()
    report["database_size"] = {
        "human_readable": size_data[0],
        "bytes": size_data[1]
    }
    
    # Table statistics
    cur.execute("""
        SELECT schemaname, tablename,
               pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
               n_tup_ins, n_tup_upd, n_tup_del, n_live_tup, n_dead_tup
        FROM pg_stat_user_tables
        JOIN pg_tables ON pg_stat_user_tables.tablename = pg_tables.tablename
        ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
    """)
    
    tables = cur.fetchall()
    report["table_stats"] = [
        {
            "table": f"{row[0]}.{row[1]}",
            "size": row[2],
            "inserts": row[3],
            "updates": row[4],
            "deletes": row[5],
            "live_tuples": row[6],
            "dead_tuples": row[7]
        }
        for row in tables
    ]
    
    # Slow queries (last 24 hours)
    cur.execute("""
        SELECT query, calls, total_time, mean_time, rows
        FROM pg_stat_statements
        WHERE mean_time > 100
        ORDER BY total_time DESC
        LIMIT 10
    """)
    
    slow_queries = cur.fetchall()
    report["slow_queries"] = [
        {
            "query": row[0][:200] + "..." if len(row[0]) > 200 else row[0],
            "calls": row[1],
            "total_time_ms": row[2],
            "avg_time_ms": row[3],
            "rows_affected": row[4]
        }
        for row in slow_queries
    ]
    
    conn.close()
    
    # Save report
    report_file = f"/var/log/mytypist/db_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"📊 Database performance report saved: {report_file}")
    return report

if __name__ == "__main__":
    generate_performance_report()
```

---

## High Availability Setup

### 1. Master-Slave Replication
```bash
# Master server configuration
# Add to postgresql.conf
wal_level = replica
max_wal_senders = 3
wal_keep_segments = 32
archive_mode = on
archive_command = 'cp %p /var/lib/postgresql/archive/%f'

# Add to pg_hba.conf
host replication replica_user slave_ip/32 md5

# Create replication user
sudo -u postgres psql << EOF
CREATE USER replica_user REPLICATION LOGIN PASSWORD 'replica_password';
EOF
```

### 2. Connection Pooling with PgBouncer
```ini
# /etc/pgbouncer/pgbouncer.ini
[databases]
mytypist_prod = host=localhost port=5432 dbname=mytypist_prod

[pgbouncer]
listen_port = 6432
listen_addr = localhost
auth_type = md5
auth_file = /etc/pgbouncer/userlist.txt
pool_mode = transaction
server_reset_query = DISCARD ALL
max_client_conn = 1000
default_pool_size = 25
reserve_pool_size = 5
reserve_pool_timeout = 3
server_lifetime = 3600
server_idle_timeout = 600
log_connections = 1
log_disconnections = 1
```

---

## Monitoring and Alerting

### 1. Database Monitoring Queries
```sql
-- Create monitoring views
CREATE OR REPLACE VIEW database_health AS
SELECT 
    'connections' as metric,
    count(*) as value,
    200 as threshold
FROM pg_stat_activity
UNION ALL
SELECT 
    'active_connections' as metric,
    count(*) as value,
    150 as threshold
FROM pg_stat_activity 
WHERE state = 'active'
UNION ALL
SELECT 
    'idle_connections' as metric,
    count(*) as value,
    50 as threshold
FROM pg_stat_activity 
WHERE state = 'idle';

-- Monitor table bloat
CREATE OR REPLACE VIEW table_bloat AS
SELECT schemaname, tablename,
       pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as total_size,
       pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) as table_size,
       ROUND(100 * pg_total_relation_size(schemaname||'.'||tablename) / 
             NULLIF(pg_relation_size(schemaname||'.'||tablename), 0), 2) as bloat_ratio
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

### 2. Automated Health Checks
```python
# scripts/db_health_check.py
import psycopg2
import smtplib
from email.mime.text import MIMEText
from datetime import datetime

def check_database_health():
    """Comprehensive database health check"""
    health_status = {
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {},
        "alerts": []
    }
    
    try:
        conn = psycopg2.connect(os.getenv("DATABASE_URL"))
        cur = conn.cursor()
        
        # Check connection count
        cur.execute("SELECT count(*) FROM pg_stat_activity")
        connection_count = cur.fetchone()[0]
        health_status["checks"]["connections"] = connection_count
        
        if connection_count > 150:
            health_status["alerts"].append({
                "type": "HIGH_CONNECTION_COUNT",
                "value": connection_count,
                "threshold": 150
            })
        
        # Check slow queries
        cur.execute("""
            SELECT count(*) FROM pg_stat_activity 
            WHERE state = 'active' AND query_start < now() - interval '30 seconds'
        """)
        slow_queries = cur.fetchone()[0]
        health_status["checks"]["slow_queries"] = slow_queries
        
        if slow_queries > 5:
            health_status["alerts"].append({
                "type": "SLOW_QUERIES_DETECTED",
                "value": slow_queries,
                "threshold": 5
            })
        
        # Check database size
        cur.execute("SELECT pg_database_size('mytypist_prod')")
        db_size = cur.fetchone()[0]
        health_status["checks"]["database_size_gb"] = round(db_size / (1024**3), 2)
        
        conn.close()
        
    except Exception as e:
        health_status["error"] = str(e)
        health_status["alerts"].append({
            "type": "DATABASE_CONNECTION_FAILED",
            "error": str(e)
        })
    
    # Send alerts if any
    if health_status["alerts"]:
        send_alert_email(health_status)
    
    return health_status

def send_alert_email(health_status):
    """Send email alert for database issues"""
    subject = f"MyTypist Database Alert - {len(health_status['alerts'])} issues"
    
    body = f"""
    Database Health Alert
    Timestamp: {health_status['timestamp']}
    
    Alerts:
    """
    
    for alert in health_status["alerts"]:
        body += f"- {alert['type']}: {alert.get('value', 'N/A')}\n"
    
    # Send email (configure SMTP settings)
    try:
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = 'alerts@mytypist.com'
        msg['To'] = 'admin@mytypist.com'
        
        smtp = smtplib.SMTP('localhost', 587)
        smtp.send_message(msg)
        smtp.quit()
    except Exception as e:
        print(f"Failed to send alert email: {e}")

if __name__ == "__main__":
    health_status = check_database_health()
    print(json.dumps(health_status, indent=2))
```

---

## Migration Strategies

### 1. Zero-Downtime Migration
```python
# scripts/zero_downtime_migration.py
import time
from alembic import command
from alembic.config import Config
from database import engine

def run_zero_downtime_migration():
    """Run database migration with minimal downtime"""
    
    # Step 1: Prepare migration
    print("📋 Preparing migration...")
    alembic_cfg = Config("alembic.ini")
    
    # Step 2: Create migration script
    print("📝 Generating migration...")
    command.revision(alembic_cfg, autogenerate=True, message="Zero downtime migration")
    
    # Step 3: Apply migration
    print("🔄 Applying migration...")
    command.upgrade(alembic_cfg, "head")
    
    # Step 4: Verify migration
    print("✅ Verifying migration...")
    with engine.connect() as conn:
        result = conn.execute("SELECT version()")
        print(f"Database version: {result.fetchone()[0]}")
    
    print("✅ Zero-downtime migration completed")

if __name__ == "__main__":
    run_zero_downtime_migration()
```

This comprehensive database configuration guide ensures optimal performance, security, and reliability for MyTypist Backend across all environments.