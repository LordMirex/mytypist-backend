"""
Input validation utilities
"""

import re
import mimetypes
from typing import List, Optional, Dict, Any
from pathlib import Path
from fastapi import UploadFile, HTTPException, status
import magic


def validate_template_metadata(metadata: Dict[str, Any]) -> bool:
    """Validate template metadata structure"""
    try:
        # Basic validation for template metadata
        required_fields = ['name', 'description', 'category']
        
        for field in required_fields:
            if field not in metadata:
                return False
                
        # Validate field types
        if not isinstance(metadata.get('name'), str):
            return False
        if not isinstance(metadata.get('description'), str):
            return False
        if not isinstance(metadata.get('category'), str):
            return False
            
        return True
    except Exception:
        return False


def validate_file_upload(
    file: UploadFile,
    allowed_extensions: List[str],
    max_size: int,
    allowed_mime_types: Optional[List[str]] = None
) -> bool:
    """Validate uploaded file"""
    
    # Check file extension
    file_extension = Path(file.filename).suffix.lower()
    if file_extension not in [ext.lower() for ext in allowed_extensions]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type not allowed. Allowed types: {', '.join(allowed_extensions)}"
        )
    
    # Check file size
    if file.size and file.size > max_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Maximum size: {max_size // (1024*1024)}MB"
        )
    
    # Check MIME type if specified
    if allowed_mime_types:
        # Get MIME type from file content
        file_content = file.file.read(2048)  # Read first 2KB
        file.file.seek(0)  # Reset file pointer
        
        try:
            detected_mime = magic.from_buffer(file_content, mime=True)
            if detected_mime not in allowed_mime_types:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid file type. Detected: {detected_mime}"
                )
        except:
            # Fallback to filename-based detection
            guessed_mime, _ = mimetypes.guess_type(file.filename)
            if guessed_mime and guessed_mime not in allowed_mime_types:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid file type. Expected: {', '.join(allowed_mime_types)}"
                )
    
    return True


def validate_email(email: str) -> bool:
    """Validate email address format"""
    
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def validate_phone(phone: str) -> bool:
    """Validate phone number format"""
    
    # Remove all non-digit characters
    digits_only = re.sub(r'\D', '', phone)
    
    # Check if it's a valid Nigerian number or international format
    if len(digits_only) >= 10 and len(digits_only) <= 15:
        return True
    
    return False


def validate_password_strength(password: str) -> Dict[str, Any]:
    """Validate password strength and return feedback"""
    
    result = {
        "is_valid": True,
        "score": 0,
        "feedback": [],
        "requirements_met": {}
    }
    
    # Length check
    if len(password) >= 8:
        result["score"] += 2
        result["requirements_met"]["min_length"] = True
    else:
        result["is_valid"] = False
        result["feedback"].append("Password must be at least 8 characters long")
        result["requirements_met"]["min_length"] = False
    
    # Uppercase letter
    if re.search(r'[A-Z]', password):
        result["score"] += 1
        result["requirements_met"]["uppercase"] = True
    else:
        result["is_valid"] = False
        result["feedback"].append("Password must contain at least one uppercase letter")
        result["requirements_met"]["uppercase"] = False
    
    # Lowercase letter
    if re.search(r'[a-z]', password):
        result["score"] += 1
        result["requirements_met"]["lowercase"] = True
    else:
        result["is_valid"] = False
        result["feedback"].append("Password must contain at least one lowercase letter")
        result["requirements_met"]["lowercase"] = False
    
    # Digit
    if re.search(r'\d', password):
        result["score"] += 1
        result["requirements_met"]["digit"] = True
    else:
        result["is_valid"] = False
        result["feedback"].append("Password must contain at least one digit")
        result["requirements_met"]["digit"] = False
    
    # Special character
    if re.search(r'[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]', password):
        result["score"] += 1
        result["requirements_met"]["special_char"] = True
    else:
        result["is_valid"] = False
        result["feedback"].append("Password must contain at least one special character")
        result["requirements_met"]["special_char"] = False
    
    # Additional security checks
    
    # No common passwords
    common_passwords = [
        "password", "123456", "qwerty", "abc123", "password123",
        "admin", "letmein", "welcome", "monkey", "dragon"
    ]
    
    if password.lower() in common_passwords:
        result["is_valid"] = False
        result["feedback"].append("Password is too common")
        result["score"] -= 2
    
    # No repeated characters
    if re.search(r'(.)\1{2,}', password):
        result["feedback"].append("Avoid repeating characters")
        result["score"] -= 1
    
    # No sequential characters
    sequences = ["123", "abc", "qwe", "asd", "zxc"]
    if any(seq in password.lower() for seq in sequences):
        result["feedback"].append("Avoid sequential characters")
        result["score"] -= 1
    
    # Calculate final score (0-10)
    result["score"] = max(0, min(10, result["score"]))
    
    return result


def validate_username(username: str) -> Dict[str, Any]:
    """Validate username format and availability"""
    
    result = {
        "is_valid": True,
        "feedback": []
    }
    
    # Length check
    if len(username) < 3 or len(username) > 50:
        result["is_valid"] = False
        result["feedback"].append("Username must be between 3 and 50 characters")
    
    # Character check
    if not re.match(r'^[a-zA-Z0-9_-]+$', username):
        result["is_valid"] = False
        result["feedback"].append("Username can only contain letters, numbers, underscores, and hyphens")
    
    # Must start with letter or number
    if not re.match(r'^[a-zA-Z0-9]', username):
        result["is_valid"] = False
        result["feedback"].append("Username must start with a letter or number")
    
    # Reserved usernames
    reserved = [
        "admin", "root", "administrator", "system", "test", "user",
        "api", "www", "mail", "ftp", "support", "help", "info",
        "mytypist", "app", "application"
    ]
    
    if username.lower() in reserved:
        result["is_valid"] = False
        result["feedback"].append("Username is reserved")
    
    return result


def validate_document_title(title: str) -> bool:
    """Validate document title"""
    
    if not title or len(title.strip()) == 0:
        return False
    
    if len(title) > 255:
        return False
    
    # Check for dangerous characters
    dangerous_chars = ['<', '>', '"', "'", '&', '\\', '/', '|']
    if any(char in title for char in dangerous_chars):
        return False
    
    return True


def validate_template_category(category: str) -> bool:
    """Validate template category"""
    
    valid_categories = [
        "contracts", "letters", "invoices", "agreements", "forms",
        "certificates", "reports", "proposals", "legal", "business",
        "personal", "academic", "government", "medical", "other"
    ]
    
    return category.lower() in valid_categories


def validate_placeholder_name(name: str) -> bool:
    """Validate placeholder name"""
    
    # Must be valid identifier
    if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]*$', name):
        return False
    
    # Length check
    if len(name) < 1 or len(name) > 100:
        return False
    
    # Reserved names
    reserved = [
        "id", "class", "style", "script", "iframe", "object", "embed",
        "form", "input", "button", "select", "textarea"
    ]
    
    if name.lower() in reserved:
        return False
    
    return True


def validate_json_data(data: Any) -> bool:
    """Validate JSON data structure"""
    
    try:
        import json
        
        # Try to serialize and deserialize
        json_str = json.dumps(data)
        json.loads(json_str)
        
        # Check size limit (1MB)
        if len(json_str.encode('utf-8')) > 1024 * 1024:
            return False
        
        return True
    
    except (TypeError, ValueError):
        return False


def sanitize_html_input(text: str) -> str:
    """Sanitize HTML input to prevent XSS"""
    
    import html
    
    # HTML escape
    sanitized = html.escape(text)
    
    # Remove dangerous tags even if escaped
    dangerous_patterns = [
        r'&lt;script.*?&gt;.*?&lt;/script&gt;',
        r'&lt;iframe.*?&gt;.*?&lt;/iframe&gt;',
        r'&lt;object.*?&gt;.*?&lt;/object&gt;',
        r'&lt;embed.*?&gt;.*?&lt;/embed&gt;',
        r'javascript:',
        r'vbscript:',
        r'on\w+\s*='
    ]
    
    for pattern in dangerous_patterns:
        sanitized = re.sub(pattern, '', sanitized, flags=re.IGNORECASE | re.DOTALL)
    
    return sanitized


def validate_url(url: str) -> bool:
    """Validate URL format"""
    
    pattern = r'^https?://(?:[-\w.])+(?:\:[0-9]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:\#(?:[\w.])*)?)?$'
    return re.match(pattern, url) is not None


def validate_currency_amount(amount: float, currency: str = "NGN") -> bool:
    """Validate currency amount"""
    
    # Must be positive
    if amount <= 0:
        return False
    
    # Must not exceed reasonable limits
    if currency == "NGN":
        # Maximum 100 million Naira
        if amount > 100_000_000:
            return False
        
        # Minimum 1 Naira
        if amount < 1:
            return False
    
    # Check for reasonable decimal places (max 2)
    if round(amount, 2) != amount:
        return False
    
    return True


def validate_business_rules(data: Dict[str, Any], rules: Dict[str, Any]) -> Dict[str, Any]:
    """Validate business rules"""
    
    result = {
        "is_valid": True,
        "violations": []
    }
    
    for rule_name, rule_config in rules.items():
        rule_type = rule_config.get("type")
        field = rule_config.get("field")
        value = data.get(field)
        
        if rule_type == "required" and not value:
            result["is_valid"] = False
            result["violations"].append(f"{field} is required")
        
        elif rule_type == "min_value" and value is not None:
            min_val = rule_config.get("value")
            if value < min_val:
                result["is_valid"] = False
                result["violations"].append(f"{field} must be at least {min_val}")
        
        elif rule_type == "max_value" and value is not None:
            max_val = rule_config.get("value")
            if value > max_val:
                result["is_valid"] = False
                result["violations"].append(f"{field} must not exceed {max_val}")
        
        elif rule_type == "pattern" and value is not None:
            pattern = rule_config.get("value")
            if not re.match(pattern, str(value)):
                result["is_valid"] = False
                result["violations"].append(f"{field} format is invalid")
        
        elif rule_type == "custom" and value is not None:
            validator_func = rule_config.get("validator")
            if validator_func and not validator_func(value):
                result["is_valid"] = False
                result["violations"].append(rule_config.get("message", f"{field} is invalid"))
    
    return result
