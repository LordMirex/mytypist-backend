"""
Pydantic schemas for request/response validation
"""

from .user import (
    UserBase, UserCreate, UserUpdate, UserResponse, UserLogin,
    UserPasswordChange, UserProfile, UserSettings
)
from .template import (
    TemplateBase, TemplateCreate, TemplateUpdate, TemplateResponse,
    TemplateList, PlaceholderCreate, PlaceholderResponse
)
from .document import (
    DocumentBase, DocumentCreate, DocumentUpdate, DocumentResponse,
    DocumentList, DocumentGenerate, DocumentShare
)
from .signature import (
    SignatureBase, SignatureCreate, SignatureResponse,
    SignatureVerify, SignatureRequest
)
from .payment import (
    PaymentCreate, PaymentResponse, PaymentWebhook,
    SubscriptionCreate, SubscriptionResponse, SubscriptionUpdate,
    InvoiceResponse
)

__all__ = [
    # User schemas
    "UserBase", "UserCreate", "UserUpdate", "UserResponse", "UserLogin",
    "UserPasswordChange", "UserProfile", "UserSettings",
    
    # Template schemas
    "TemplateBase", "TemplateCreate", "TemplateUpdate", "TemplateResponse",
    "TemplateList", "PlaceholderCreate", "PlaceholderResponse",
    
    # Document schemas
    "DocumentBase", "DocumentCreate", "DocumentUpdate", "DocumentResponse",
    "DocumentList", "DocumentGenerate", "DocumentShare",
    
    # Signature schemas
    "SignatureBase", "SignatureCreate", "SignatureResponse",
    "SignatureVerify", "SignatureRequest",
    
    # Payment schemas
    "PaymentCreate", "PaymentResponse", "PaymentWebhook",
    "SubscriptionCreate", "SubscriptionResponse", "SubscriptionUpdate",
    "InvoiceResponse"
]
