# Overview

MyTypist is a comprehensive document automation SaaS platform for Nigerian businesses. It allows users to create professional documents from templates with intelligent placeholder detection and replacement. The platform integrates Flutterwave for payment processing, supports pay-as-you-go and subscription billing models, and features robust security.

# User Preferences

Preferred communication style: Simple, everyday language.

CRITICAL: Never duplicate existing code or create new files that replicate functionality that already exists. Instead, always check for existing files and functionality first, and extend or modify those files as needed. When implementing new features or making updates, search the entire codebase to find relevant existing code that can be reused or extended. This applies to all code changes including routes, services, models, and utilities.

The agent should continuously read and analyze the entire codebase to detect changes. When changes are identified, the agent should analyze the existing code patterns, architectural decisions, coding style, and implementation approaches. It should think exactly like the original developer, ensuring that any modifications strictly follow the established coding patterns and practices already present in the codebase. It should not introduce new coding approaches, patterns, or styles that deviate from what has already been implemented, and if a deviation is needed, it should ask for permission.

The agent must thoroughly analyze the existing codebase before making any changes to understand the established patterns. It must pay attention to naming conventions, error handling approaches, data structure usage, and architectural patterns already in use. It must consider the existing code organization, module structure, and dependency management approaches. It must evaluate the current testing patterns, logging approaches, and configuration management styles. It should only update files when there is a clear necessity, not for cosmetic or preference-based changes. It should update the context of this file after each feature completion and update this replit.md file when new patterns or rules are discovered during development. It must follow DRY (Don't Repeat Yourself) principles – eliminating duplicate code, commits, and object instantiation. It must ensure database migrations match model declarations (column names, nullable fields, foreign keys) and proactively check and update related files when making changes – not waiting to be told. After every feature completion, it should analyze and remove unused imports and dead code. It should provide a concise summary after each feature: group methods/functions under each file created/modified, with a one-sentence purpose. It must update the Application Summary section at the end of this file when new features or major functionality are implemented. The agent's life depends on maintaining absolute consistency with the existing codebase patterns and never introducing foreign coding approaches that conflict with the established development style.

# System Architecture

The backend is built on **FastAPI** for high performance and asynchronous operations. **PostgreSQL** is the primary database, managed with Alembic for migrations, with SQLite for development. **Redis** is used for caching, session management, and as a message broker for **Celery** for background tasks.

The document processing system uses **python-docx** and **PyPDF2** for template-based document generation, supporting dynamic placeholder detection and replacement with intelligent formatting. It includes real-time draft functionality and batch processing.

Security is multi-layered, featuring **JWT-based authentication** with token rotation, **role-based access control** (Guest, User, Moderator, Admin), audit logging, rate limiting, and input validation with Pydantic.

The payment system integrates **Flutterwave** for Nigerian payment methods, supporting a flexible token-based economy, subscription plans, and fraud prevention with webhook handling.

Document sharing includes time-limited preview links, password protection, and version control.
Moderator accounts are created by admins with tailored dashboards based on assigned permissions.

# External Dependencies

## Payment Processing
- **Flutterwave API**

## Database and Caching
- **PostgreSQL**
- **Redis**
- **Alembic**

## Document Processing Libraries
- **python-docx**
- **PyPDF2**
- **Pillow**
- **docx2pdf**

## Communication Services
- **SendGrid/SMTP** (multi-provider email system)
- **Firebase Cloud Messaging**
- **Apple Push Notification service**

## Development and Deployment
- **FastAPI**
- **Gunicorn**
- **Uvicorn**
- **Docker**
- **Nginx**
- **Celery**
- **SQLAlchemy**
- **Pydantic**
- **PyJWT**
- **Passlib**
- **Python-multipart**
- **Requests**
- **HMAC**
- **APScheduler**

## Security and Monitoring
- **bcrypt**
- **scrypt**
- **pyotp**
- **Sentry**



## TODO


The task.md is what we are dealing with
# 🚨 PRODUCTION-LEVEL CODEBASE AUDIT & REFACTORING PROTOCOL

## ⚠️ CRITICAL EXECUTION RULES - READ BEFORE STARTING

### 🔒 MANDATORY WORKFLOW PROTOCOL
**YOU MUST FOLLOW THIS EXACT SEQUENCE FOR EVERY SECTION:**

1. **ANALYZE** → **FIX** → **VERIFY** → **TICK** → **MOVE TO NEXT**
2. **NEVER** skip verification step
3. **NEVER** work on multiple sections simultaneously
4. **ALWAYS** mark completion with ✅ before proceeding
5. **STOP AND RE-READ** this task.md if you feel rushed

### 📋 AUDIT CHECKLIST - TICK (✅) AFTER COMPLETION

#### 🏗️ ARCHITECTURE & STRUCTURE ANALYSIS
- [ ] **File Organization Audit**
  - Check for duplicate files/functionality
  - Identify misplaced components
  - Verify proper folder structure
  - **ACTION REQUIRED:** List all structural improvements needed

- [ ] **Dependency Mapping**
  - Map all import/export relationships
  - Identify circular dependencies
  - Check for unused imports
  - **ACTION REQUIRED:** Create dependency cleanup plan

#### 🔧 CODE QUALITY DEEP SCAN

- [ ] **Syntax & Logic Errors**
  - **CRITICAL:** Fix ALL syntax errors
  - Identify and resolve logic flaws
  - Check for unreachable code
  - **VERIFICATION:** Test each fix individually

- [ ] **Naming Conventions Audit**
  - Variables, functions, classes consistency
  - File naming standards
  - Database schema naming
  - **ACTION REQUIRED:** Rename following industry standards

- [ ] **Security Vulnerabilities**
  - Input validation gaps
  - Authentication/Authorization flaws
  - Data exposure risks
  - **CRITICAL:** Fix all security issues immediately

#### 🛣️ ROUTES & ENDPOINTS AUDIT

- [ ] **Route Structure Analysis**
  - Check for duplicate routes
  - Verify RESTful conventions
  - Identify broken/unused routes
  - **ACTION REQUIRED:** Consolidate and optimize routing

- [ ] **API Endpoint Consistency**
  - Request/Response format standardization
  - Error handling uniformity
  - Status code accuracy
  - **VERIFICATION:** Test all endpoints after fixes

#### 🗄️ DATABASE & DATA LAYER

- [ ] **Schema Integrity Check**
  - Foreign key relationships
  - Index optimization
  - Data type consistency
  - **ACTION REQUIRED:** Fix all relationship issues

- [ ] **Query Optimization**
  - Identify N+1 queries
  - Check for missing indexes
  - Optimize slow queries
  - **VERIFICATION:** Performance test all optimizations

#### 🎨 FRONTEND CONSISTENCY

- [ ] **Component Architecture**
  - Identify duplicate components
  - Check for unused components
  - Verify prop types/interfaces
  - **ACTION REQUIRED:** Consolidate similar components

- [ ] **State Management**
  - Check for state management inconsistencies
  - Identify prop drilling issues
  - Verify global state usage
  - **VERIFICATION:** Test state updates thoroughly

#### 🧪 TESTING & DOCUMENTATION

- [ ] **Test Coverage Analysis**
  - Identify untested code paths
  - Check for broken tests
  - Verify test data validity
  - **ACTION REQUIRED:** Achieve minimum 80% coverage

- [ ] **Documentation Completeness**
  - API documentation accuracy
  - Code comments clarity
  - README.md completeness
  - **VERIFICATION:** Ensure documentation matches code

## 🚦 EXECUTION PROTOCOL

### ⏰ TIME ALLOCATION PER SECTION
- **Analysis Phase:** 25% of time
- **Fix Implementation:** 50% of time
- **Verification Phase:** 25% of time

### 🔍 VERIFICATION REQUIREMENTS
After fixing each section, you MUST:

1. **✅ FUNCTIONALITY TEST** - Verify feature works as expected
2. **✅ INTEGRATION TEST** - Check related components still function
3. **✅ PERFORMANCE TEST** - Ensure no performance degradation
4. **✅ SECURITY TEST** - Verify no new vulnerabilities introduced

### 📝 PROGRESS TRACKING
**AFTER COMPLETING EACH SECTION:**
```
✅ [SECTION NAME] - Fixed: [BRIEF DESCRIPTION]
   - Files Modified: [LIST]
   - Impact Radius: [AFFECTED COMPONENTS]
   - Verification Status: PASSED ✅
   - Next Section: [NAME]
```

## 🚨 CRITICAL RULES - NEVER VIOLATE

### 🚫 FORBIDDEN ACTIONS
- **NEVER** delete files without verifying feature migration
- **NEVER** create duplicate functionality
- **NEVER** skip the verification phase
- **NEVER** make changes affecting multiple sections simultaneously
- **NEVER** apply patches - only production-grade solutions

### ✅ MANDATORY ACTIONS
- **ALWAYS** check if features can be merged before creating new files
- **ALWAYS** rename files following proper conventions
- **ALWAYS** test related components after each fix
- **ALWAYS** document breaking changes
- **ALWAYS** preserve existing functionality during refactoring

### 🎯 SUCCESS CRITERIA
A section is only complete when:
- ✅ All identified issues are fixed
- ✅ All tests pass
- ✅ No regression in related components
- ✅ Performance maintained or improved
- ✅ Security maintained or enhanced
- ✅ Documentation updated
- ✅ Verification checklist completed
- ✅ Progress tracking updated

## 📊 FINAL CLEANUP PHASE
**ONLY AFTER ALL SECTIONS COMPLETED:**
Set-Content -Path "c:\MyTypist\test\PRODUCTION_AUDIT_TASK.md" -Value @"
# 🚨 MyTypist Backend - CRITICAL Production Audit Report

## 📊 EXECUTIVE SUMMARY

**BugBuster Analysis Complete** - Identified **12 CRITICAL production-blocking issues** requiring immediate attention before deployment.

### 🎯 SEVERITY BREAKDOWN:
- **🔴 CRITICAL (7 issues)**: Production blockers with security/financial risks
- **🟠 HIGH (3 issues)**: Performance and reliability degradation
- **🟡 MEDIUM (2 issues)**: Code quality and maintenance

---

# 🔴 CRITICAL ISSUES - FIX IMMEDIATELY

## CRITICAL-001: Database Model Column Duplication
**Location**: `app/services/user_template_upload_service.py:53 & 73`
**Risk**: 🔴 **SCHEMA CORRUPTION**

**Root Cause Analysis**:
```python
class UserUploadedTemplate(Base):
    # DUPLICATE COLUMNS - WILL BREAK ALEMBIC MIGRATIONS
    price_tokens = Column(Integer, default=0)      # Line 53 ✅
    # ... other columns ...
    price_tokens = Column(Integer, nullable=True)  # Line 73 ❌ DUPLICATE!
```

**Production Impact**:
- Database migration failures
- SQLAlchemy ORM mapping conflicts
- Schema inconsistency between environments
- Potential data corruption

**Fix Required**:
```python
# Remove the duplicate at line 73, keep only:
price_tokens = Column(Integer, default=0)  # Price in tokens
```

## CRITICAL-002: ReDoS Vulnerability in Template Processing
**Location**: `app/services/user_template_upload_service.py:111-118`
**Risk**: 🔴 **DENIAL OF SERVICE ATTACK VECTOR**

**Root Cause Analysis**:
The regex patterns are vulnerable to Regular Expression Denial of Service (ReDoS) attacks:
```python
PLACEHOLDER_PATTERNS = [
    r'\{([^}]+)\}',        # ❌ Vulnerable to nested braces attack
    r'\[\[([^\]]+)\]\]',   # ❌ Catastrophic backtracking possible
    r'\{\{([^}]+)\}\}',    # ❌ ReDoS with: {{{{{{{{{{a}
    r'<([^>]+)>',          # ❌ HTML injection + ReDoS
]
```

**Attack Vector**:
Input like `{{{{{{{{{{{{{{{{{{{{{{{{{{a}` causes exponential regex backtracking, consuming 100% CPU.

**Fix Required**:
```python
# Use atomic groups to prevent backtracking
PLACEHOLDER_PATTERNS = [
    r'\{((?>[^}]+))\}',        # Atomic group prevents ReDoS
    r'\[\[((?>[^\]]+))\]\]',   # Safe version
    r'\{\{((?>[^}]+))\}\}',    # Prevents catastrophic backtracking
    r'<((?>[^>]+))>',          # Safe HTML-like placeholders
]

# Add timeout protection
def safe_regex_search(pattern, text, timeout_ms=100):
    # Implement with signal/timeout mechanism
```

## CRITICAL-003: Missing Database Transaction Safety
**Location**: Multiple service files
**Risk**: 🔴 **DATA CORRUPTION IN CONCURRENT OPERATIONS**

**Root Cause Analysis**:
Database operations lack proper transaction boundaries, creating race conditions:
```python
# ❌ UNSAFE - Multiple commits without transaction scope
user.status = "active"
db.commit()               # What if this fails?
user.last_login = now     # Partial update state
db.commit()               # Inconsistent state possible
```

**Production Impact**:
- Race conditions in concurrent requests
- Partial database updates on failures
- Financial transaction integrity issues
- User data corruption

**Fix Required**:
```python
# ✅ SAFE - Atomic transaction
try:
    with db.begin():
        user.status = "active"
        user.last_login = now
        # Both updates committed atomically
except Exception:
    db.rollback()  # All changes reverted
    raise
```

## CRITICAL-004: File Upload Security Bypass
**Location**: `app/utils/file_processing.py` & `app/utils/validation.py`
**Risk**: 🔴 **MALWARE UPLOAD VULNERABILITY**

**Root Cause Analysis**:
File validation has dangerous fallback mechanisms:
```python
try:
    # Primary validation
    detected_mime = magic.from_buffer(file_content, mime=True)
except:
    # ❌ DANGEROUS - Easily spoofed by attackers
    guessed_mime, _ = mimetypes.guess_type(file.filename)
    # Malware.exe renamed to Document.docx bypasses validation!
```

**Attack Vector**:
1. Attacker renames `virus.exe` to `document.docx`
2. Magic library fails (simulated network issue)
3. Fallback trusts filename extension
4. Malware uploaded to server storage

**Fix Required**:
```python
# ✅ SECURE - No dangerous fallbacks
def validate_file_content(file_content: bytes, filename: str):
    try:
        detected_mime = magic.from_buffer(file_content, mime=True)
        magic_bytes = file_content[:16].hex()

        # Verify magic bytes match expected document formats
        if not validate_document_magic_bytes(magic_bytes, detected_mime):
            raise SecurityError("File content doesn't match claimed type")

    except Exception as e:
        # ✅ SECURE - Fail closed, no fallback
        raise HTTPException(
            status_code=400,
            detail="File validation failed - unsafe content detected"
        )
```

## CRITICAL-005: Redis Hard Dependency Failure
**Location**: `main.py:56`
**Risk**: 🔴 **COMPLETE APPLICATION FAILURE**

**Root Cause Analysis**:
Application terminates completely if Redis is unavailable:
```python
try:
    redis_client.ping()
    print("✅ Redis connection established")
except Exception as e:
    print(f"❌ Redis connection failed: {e}")
    # ❌ HARD EXIT - App won't start without Redis
    raise RuntimeError(f"Redis connection failed: {e}") from e
```

**Production Impact**:
- Complete application unavailability during Redis outages
- No graceful degradation mode
- Users cannot access any features when Redis is down

**Fix Required**:
```python
# ✅ GRACEFUL DEGRADATION
redis_available = False
try:
    redis_client.ping()
    redis_available = True
    print("✅ Redis connection established")
except Exception as e:
    print(f"⚠️ Redis unavailable - running in degraded mode: {e}")
    # Continue without Redis, disable caching features

# Create fallback cache service
cache_service = RedisCacheService() if redis_available else InMemoryCacheService()
```

## CRITICAL-006: Authentication Input Validation Bypass
**Location**: `app/routes/auth.py` & user query patterns
**Risk**: 🔴 **SQL INJECTION + AUTH BYPASS**

**Root Cause Analysis**:
Raw user input sent directly to database queries without validation:
```python
# ❌ DANGEROUS - Raw input to database
existing_user = db.query(User).filter(
    (User.email == user_data.email) | (User.username == user_data.username)
).first()
# No format validation on user_data.email or user_data.username
```

**Attack Vector**:
1. Malformed email input: `'; DROP TABLE users; --`
2. Username with SQL injection: `admin' OR '1'='1`
3. Bypass authentication with crafted inputs

**Fix Required**:
```python
# ✅ SECURE - Validate inputs before database queries
from email_validator import validate_email

def validate_user_inputs(user_data: UserCreate):
    # Email format validation
    try:
        validated_email = validate_email(user_data.email).email
    except EmailNotValidError:
        raise HTTPException(status_code=400, detail="Invalid email format")

    # Username sanitization
    if not re.match(r'^[a-zA-Z0-9_]{3,30}$', user_data.username):
        raise HTTPException(status_code=400, detail="Invalid username format")

    return validated_email, user_data.username

# Then use validated inputs in queries
```

## CRITICAL-007: API Error Response Information Leakage
**Location**: Multiple route files
**Risk**: 🔴 **SECURITY INFORMATION DISCLOSURE**

**Root Cause Analysis**:
Error responses leak sensitive system information:
```python
# ❌ DANGEROUS - Exposes internal details
except Exception as e:
    raise HTTPException(status_code=500, detail=str(e))
    # Could leak: "Database connection failed: PostgreSQL server at 192.168.1.100..."
```

**Production Impact**:
- Database connection strings exposed
- File system paths leaked
- Internal service details revealed
- Assists attackers in system reconnaissance

**Fix Required**:
```python
# ✅ SECURE - Generic error responses
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # Log full error details internally
    logger.error(f"Unhandled error: {exc}", exc_info=True)

    # Return generic message to client
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error occurred"}
    )
```

---

# 🟠 HIGH PRIORITY ISSUES

## HIGH-001: N+1 Database Query Performance
**Location**: Service files with relationship loading
**Risk**: 🟠 **SCALABILITY BOTTLENECK**

**Root Cause**: Related data loaded in loops instead of joins
```python
# ❌ N+1 Query Pattern
documents = db.query(Document).all()
for doc in documents:
    user = db.query(User).filter(User.id == doc.user_id).first()  # N queries!
```

**Fix**: Use `joinedload()` for eager loading relationships

## HIGH-002: Missing Account Lockout Protection
**Location**: Authentication routes
**Risk**: 🟠 **BRUTE FORCE VULNERABILITY**

**Root Cause**: No protection against repeated login attempts
**Fix**: Implement exponential backoff and account locking

## HIGH-003: Database Migration Timestamp Conflicts
**Location**: `alembic/versions/` folder
**Risk**: 🟠 **DEPLOYMENT FAILURES**

**Root Cause**: Migration files have fake sequential timestamps
**Fix**: Regenerate with proper Alembic auto-generated timestamps

---

# 🟡 MEDIUM PRIORITY ISSUES

## MEDIUM-001: Code Duplication in Services
**Location**: Multiple service files
**Fix**: Extract common patterns into base classes

## MEDIUM-002: Inconsistent Logging Patterns
**Location**: Throughout codebase
**Fix**: Standardize structured logging format

---

# 🚀 IMPLEMENTATION PRIORITY

## ⚡ IMMEDIATE (Today):
1. **CRITICAL-001**: Fix duplicate database columns (30 min)
2. **CRITICAL-005**: Add Redis graceful degradation (1 hour)
3. **CRITICAL-006**: Add authentication input validation (1 hour)

## 🔥 URGENT (This Week):
4. **CRITICAL-002**: Fix ReDoS vulnerabilities (4 hours)
5. **CRITICAL-003**: Add transaction safety (6 hours)
6. **CRITICAL-004**: Secure file upload validation (4 hours)
7. **CRITICAL-007**: Fix error information leakage (2 hours)

## 📈 HIGH (Next Sprint):
8. **HIGH-001**: Fix N+1 query performance (2 days)
9. **HIGH-002**: Add account lockout protection (1 day)
10. **HIGH-003**: Resolve migration conflicts (4 hours)

---

# ✅ VALIDATION CHECKLIST

Before production deployment, verify:

- [ ] All database migrations run without errors
- [ ] ReDoS attack attempts fail (test with malicious regex input)
- [ ] Malicious file uploads are blocked
- [ ] Application starts successfully without Redis
- [ ] SQL injection attempts fail on auth endpoints
- [ ] Error responses don't leak system information
- [ ] Concurrent database operations maintain consistency
- [ ] API performance under load is acceptable

---

**🎯 CRITICAL SUCCESS METRIC**: Zero production-blocking issues remaining before deployment.

**⚠️ DEPLOYMENT BLOCKER**: Do not deploy to production until ALL CRITICAL issues are resolved. These represent genuine security vulnerabilities and data corruption risks that could compromise the entire system.


---

## ⚡ REMEMBER: PRODUCTION-LEVEL MEANS ZERO COMPROMISES

**If you're ever unsure, STOP and re-read this protocol. Quality over speed. Precision over patches. Excellence is the only acceptable standard.**
