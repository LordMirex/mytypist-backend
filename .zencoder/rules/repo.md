---
description: Repository Information Overview
alwaysApply: true
---


# MyTypist Backend Information

## Summary
MyTypist is a high-performance document automation SaaS platform designed for Nigerian businesses. It provides document generation, template management, and collaboration features with Flutterwave payment integration. The platform is built with FastAPI, PostgreSQL, and Redis, focusing on security, scalability, and performance.

## Structure
- **app/**: Core application code (models, routes, services, utils)
- **alembic/**: Database migration scripts and configuration
- **docs/**: Comprehensive documentation and guides
- **storage/**: Document and template storage directories
- **.vscode/**: VS Code configuration
- **tests/**: Located within app directory, contains all test files

## Language & Runtime
**Language**: Python
**Version**: Python 3.11+
**Framework**: FastAPI 0.116.1+
**Build System**: Standard Python packaging
**Package Manager**: pip/uv (uv.lock present)

## Dependencies
**Main Dependencies**:
- FastAPI (0.116.1+): Web framework
- SQLAlchemy (2.0.43+): ORM for database operations
- Alembic (1.16.5+): Database migrations
- Redis (6.4.0+): Caching and session management
- Celery (5.5.3+): Background task processing
- Uvicorn (0.35.0+): ASGI server
- Pydantic (2.11.7+): Data validation
- Python-jose (3.5.0+): JWT authentication
- Psycopg2 (2.9.10+): PostgreSQL adapter

**Document Processing**:
- python-docx (1.1.2+): DOCX processing
- PyPDF2 (3.0.1+): PDF manipulation
- Pillow (11.3.0+): Image processing
- Jinja2 (3.1.6+): Template rendering

## Build & Installation
```bash
# Install dependencies
pip install -e .

# Run development server
python main.py

# Run with production server
gunicorn -c gunicorn.conf.py main:app
```

## Docker
**Configuration**: Docker Compose setup for PostgreSQL database
**Docker Compose**: docker-compose.yml defines PostgreSQL 16 service
**Environment**: Uses environment variables for configuration

## Database
**Type**: PostgreSQL 16
**ORM**: SQLAlchemy 2.0+
**Migrations**: Alembic for schema management
**Connection**: Configured in database.py and config.py

## Testing
**Framework**: pytest 8.0.0+
**Test Location**: app/tests/
**Naming Convention**: test_*.py files
**Configuration**: pytest.ini and conftest.py
**Run Command**:
```bash
pytest
# Or with specific markers
pytest -m "not slow"
```

## API Structure
**Authentication**: JWT-based with role-based access control
**Routes**: Organized by feature (auth, documents, templates, etc.)
**Middleware**: Security, rate limiting, audit logging, performance monitoring
**Documentation**: Available at /api/docs in debug mode

## Performance Features
- Redis caching for high-performance operations
- Celery for background task processing
- Uvicorn with uvloop for async performance
- Gunicorn for production deployment with worker management
- Compression middleware for response optimization---
description: Repository Information Overview
alwaysApply: true
---

# MyTypist Backend Information

## Summary
MyTypist is a high-performance document automation SaaS platform designed for Nigerian businesses. It provides document generation, template management, and collaboration features with Flutterwave payment integration. The platform is built with FastAPI, PostgreSQL, and Redis, focusing on security, scalability, and performance.

## Structure
- **app/**: Core application code (models, routes, services, utils)
- **alembic/**: Database migration scripts and configuration
- **docs/**: Comprehensive documentation and guides
- **storage/**: Document and template storage directories
- **.vscode/**: VS Code configuration
- **tests/**: Located within app directory, contains all test files

## Language & Runtime
**Language**: Python
**Version**: Python 3.11+
**Framework**: FastAPI 0.116.1+
**Build System**: Standard Python packaging
**Package Manager**: pip/uv (uv.lock present)

## Dependencies
**Main Dependencies**:
- FastAPI (0.116.1+): Web framework
- SQLAlchemy (2.0.43+): ORM for database operations
- Alembic (1.16.5+): Database migrations
- Redis (6.4.0+): Caching and session management
- Celery (5.5.3+): Background task processing
- Uvicorn (0.35.0+): ASGI server
- Pydantic (2.11.7+): Data validation
- Python-jose (3.5.0+): JWT authentication
- Psycopg2 (2.9.10+): PostgreSQL adapter

**Document Processing**:
- python-docx (1.1.2+): DOCX processing
- PyPDF2 (3.0.1+): PDF manipulation
- Pillow (11.3.0+): Image processing
- Jinja2 (3.1.6+): Template rendering

## Build & Installation
```bash
# Install dependencies
pip install -e .

# Run development server
python main.py

# Run with production server
gunicorn -c gunicorn.conf.py main:app
```

## Docker
**Configuration**: Docker Compose setup for PostgreSQL database
**Docker Compose**: docker-compose.yml defines PostgreSQL 16 service
**Environment**: Uses environment variables for configuration

## Database
**Type**: PostgreSQL 16
**ORM**: SQLAlchemy 2.0+
**Migrations**: Alembic for schema management
**Connection**: Configured in database.py and config.py

## Testing
**Framework**: pytest 8.0.0+
**Test Location**: app/tests/
**Naming Convention**: test_*.py files
**Configuration**: pytest.ini and conftest.py
**Run Command**:
```bash
pytest
# Or with specific markers
pytest -m "not slow"
```

## API Structure
**Authentication**: JWT-based with role-based access control
**Routes**: Organized by feature (auth, documents, templates, etc.)
**Middleware**: Security, rate limiting, audit logging, performance monitoring
**Documentation**: Available at /api/docs in debug mode

## Performance Featurescd c:\MyTypist\test

- Redis caching for high-performance operations
- Celery for background task processing
- Uvicorn with uvloop for async performance
- Gunicorn for production deployment with worker management
- Compression middleware for response optimization
