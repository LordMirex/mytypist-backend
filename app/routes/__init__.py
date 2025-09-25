"""
API routes for MyTypist backend
"""

# Import all routers to make them available
from . import (
    auth, documents, templates, signatures, analytics, 
    payments, admin, feedback, role_management, 
    moderator_management
)

__all__ = [
    "auth", "documents", "templates", "signatures",
    "analytics", "payments", "admin", "feedback",
    "role_management", "moderator_management"
]
