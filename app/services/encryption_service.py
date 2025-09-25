"""
File encryption and security service
"""

import os
import hashlib
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path
import base64

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from config import settings


class EncryptionService:
    """File and data encryption service"""
    
    # Master encryption key (in production, store in secure key management)
    MASTER_KEY = settings.SECRET_KEY.encode()[:32].ljust(32, b'0')
    
    @staticmethod
    def generate_key() -> bytes:
        """Generate a new encryption key"""
        return Fernet.generate_key()
    
    @staticmethod
    def get_encryption_key(key_id: str = "default") -> bytes:
        """Get encryption key by ID"""
        
        if key_id == "default":
            # Derive key from master key
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=b"mytypist_salt",
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(EncryptionService.MASTER_KEY))
            return key
        
        # In production, retrieve from secure key store
        # For now, generate deterministic key from ID
        key_hash = hashlib.sha256(f"{key_id}{settings.SECRET_KEY}".encode()).digest()
        return base64.urlsafe_b64encode(key_hash)
    
    @staticmethod
    async def encrypt_file(file_path: str, key_id: str = "default") -> Optional[str]:
        """Encrypt a file and return encrypted file path"""
        
        try:
            if not os.path.exists(file_path):
                return None
            
            # Get encryption key
            encryption_key = EncryptionService.get_encryption_key(key_id)
            fernet = Fernet(encryption_key)
            
            # Read original file
            with open(file_path, 'rb') as file:
                file_data = file.read()
            
            # Encrypt data
            encrypted_data = fernet.encrypt(file_data)
            
            # Create encrypted file path
            encrypted_file_path = file_path + '.encrypted'
            
            # Write encrypted data
            with open(encrypted_file_path, 'wb') as encrypted_file:
                encrypted_file.write(encrypted_data)
            
            # Remove original file
            os.remove(file_path)
            
            return encrypted_file_path
            
        except Exception as e:
            print(f"Encryption error: {e}")
            return None
    
    @staticmethod
    async def decrypt_file(encrypted_file_path: str, key_id: str = "default") -> Optional[str]:
        """Decrypt a file and return decrypted file path"""
        
        try:
            if not os.path.exists(encrypted_file_path):
                return None
            
            # Get encryption key
            encryption_key = EncryptionService.get_encryption_key(key_id)
            fernet = Fernet(encryption_key)
            
            # Read encrypted file
            with open(encrypted_file_path, 'rb') as encrypted_file:
                encrypted_data = encrypted_file.read()
            
            # Decrypt data
            decrypted_data = fernet.decrypt(encrypted_data)
            
            # Create decrypted file path
            decrypted_file_path = encrypted_file_path.replace('.encrypted', '')
            
            # Write decrypted data
            with open(decrypted_file_path, 'wb') as decrypted_file:
                decrypted_file.write(decrypted_data)
            
            return decrypted_file_path
            
        except Exception as e:
            print(f"Decryption error: {e}")
            return None
    
    @staticmethod
    def encrypt_string(data: str, key_id: str = "default") -> str:
        """Encrypt a string"""
        
        try:
            encryption_key = EncryptionService.get_encryption_key(key_id)
            fernet = Fernet(encryption_key)
            
            encrypted_data = fernet.encrypt(data.encode())
            return base64.urlsafe_b64encode(encrypted_data).decode()
            
        except Exception as e:
            print(f"String encryption error: {e}")
            return data
    
    @staticmethod
    def decrypt_string(encrypted_data: str, key_id: str = "default") -> str:
        """Decrypt a string"""
        
        try:
            encryption_key = EncryptionService.get_encryption_key(key_id)
            fernet = Fernet(encryption_key)
            
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_data.encode())
            decrypted_data = fernet.decrypt(encrypted_bytes)
            return decrypted_data.decode()
            
        except Exception as e:
            print(f"String decryption error: {e}")
            return encrypted_data
    
    @staticmethod
    def hash_data(data: str, algorithm: str = "sha256") -> str:
        """Hash data using specified algorithm"""
        
        if algorithm == "sha256":
            return hashlib.sha256(data.encode()).hexdigest()
        elif algorithm == "md5":
            return hashlib.md5(data.encode()).hexdigest()
        elif algorithm == "sha512":
            return hashlib.sha512(data.encode()).hexdigest()
        else:
            return hashlib.sha256(data.encode()).hexdigest()
    
    @staticmethod
    def verify_file_integrity(file_path: str, expected_hash: str) -> bool:
        """Verify file integrity using hash"""
        
        try:
            if not os.path.exists(file_path):
                return False
            
            # Calculate file hash
            file_hash = EncryptionService.calculate_file_hash(file_path)
            return file_hash == expected_hash
            
        except Exception:
            return False
    
    @staticmethod
    def calculate_file_hash(file_path: str, algorithm: str = "sha256") -> str:
        """Calculate hash of file"""
        
        if algorithm == "sha256":
            hash_func = hashlib.sha256()
        elif algorithm == "md5":
            hash_func = hashlib.md5()
        elif algorithm == "sha512":
            hash_func = hashlib.sha512()
        else:
            hash_func = hashlib.sha256()
        
        try:
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_func.update(chunk)
            return hash_func.hexdigest()
        except Exception:
            return ""
    
    @staticmethod
    def secure_delete_file(file_path: str, passes: int = 3) -> bool:
        """Securely delete file by overwriting multiple times"""
        
        try:
            if not os.path.exists(file_path):
                return True
            
            file_size = os.path.getsize(file_path)
            
            with open(file_path, "r+b") as file:
                for _ in range(passes):
                    # Overwrite with random data
                    file.seek(0)
                    file.write(os.urandom(file_size))
                    file.flush()
                    os.fsync(file.fileno())
            
            # Finally, delete the file
            os.remove(file_path)
            return True
            
        except Exception as e:
            print(f"Secure delete error: {e}")
            return False
    
    @staticmethod
    def encrypt_sensitive_data(data: Dict[str, Any]) -> Dict[str, Any]:
        """Encrypt sensitive fields in data dictionary"""
        
        sensitive_fields = [
            'password', 'token', 'secret', 'key', 'credit_card',
            'ssn', 'phone', 'email', 'address', 'signature_data'
        ]
        
        encrypted_data = data.copy()
        
        for field, value in data.items():
            if any(sensitive in field.lower() for sensitive in sensitive_fields):
                if isinstance(value, str):
                    encrypted_data[field] = EncryptionService.encrypt_string(value)
        
        return encrypted_data
    
    @staticmethod
    def decrypt_sensitive_data(data: Dict[str, Any]) -> Dict[str, Any]:
        """Decrypt sensitive fields in data dictionary"""
        
        sensitive_fields = [
            'password', 'token', 'secret', 'key', 'credit_card',
            'ssn', 'phone', 'email', 'address', 'signature_data'
        ]
        
        decrypted_data = data.copy()
        
        for field, value in data.items():
            if any(sensitive in field.lower() for sensitive in sensitive_fields):
                if isinstance(value, str):
                    decrypted_data[field] = EncryptionService.decrypt_string(value)
        
        return decrypted_data
    
    @staticmethod
    def generate_secure_token(length: int = 32) -> str:
        """Generate cryptographically secure random token"""
        
        return base64.urlsafe_b64encode(os.urandom(length)).decode()
    
    @staticmethod
    def create_file_fingerprint(file_path: str) -> Dict[str, Any]:
        """Create comprehensive file fingerprint for integrity checking"""
        
        try:
            if not os.path.exists(file_path):
                return {}
            
            stat = os.stat(file_path)
            
            fingerprint = {
                "file_path": file_path,
                "size": stat.st_size,
                "created_at": datetime.fromtimestamp(stat.st_ctime),
                "modified_at": datetime.fromtimestamp(stat.st_mtime),
                "sha256_hash": EncryptionService.calculate_file_hash(file_path, "sha256"),
                "md5_hash": EncryptionService.calculate_file_hash(file_path, "md5")
            }
            
            return fingerprint
            
        except Exception as e:
            print(f"Fingerprint error: {e}")
            return {}
    
    @staticmethod
    def verify_file_fingerprint(file_path: str, fingerprint: Dict[str, Any]) -> bool:
        """Verify file against stored fingerprint"""
        
        current_fingerprint = EncryptionService.create_file_fingerprint(file_path)
        
        if not current_fingerprint:
            return False
        
        # Check critical fields
        return (
            current_fingerprint.get("size") == fingerprint.get("size") and
            current_fingerprint.get("sha256_hash") == fingerprint.get("sha256_hash")
        )
    
    @staticmethod
    def cleanup_temporary_files():
        """Cleanup temporary decrypted files (background task)"""
        
        try:
            # Find temporary files older than 1 hour
            temp_extensions = ['.tmp', '.temp', '.decrypted']
            current_time = datetime.now()
            
            for directory in [settings.DOCUMENTS_PATH, settings.TEMPLATES_PATH]:
                if not os.path.exists(directory):
                    continue
                
                for file_path in Path(directory).rglob("*"):
                    if file_path.is_file():
                        # Check if it's a temporary file
                        if any(str(file_path).endswith(ext) for ext in temp_extensions):
                            # Check age
                            file_age = current_time - datetime.fromtimestamp(file_path.stat().st_mtime)
                            if file_age.total_seconds() > 3600:  # 1 hour
                                EncryptionService.secure_delete_file(str(file_path))
        
        except Exception as e:
            print(f"Cleanup error: {e}")
    
    @staticmethod
    def rotate_encryption_keys():
        """Rotate encryption keys (security maintenance)"""
        
        # In production, this would:
        # 1. Generate new keys
        # 2. Re-encrypt data with new keys
        # 3. Update key references
        # 4. Securely dispose of old keys
        
        # For now, this is a placeholder
        print("Key rotation would be implemented here")
