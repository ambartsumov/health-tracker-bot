"""
Security and logging module for Health Bot.
Handles secure data storage, audit logging, and privacy protection.
"""

import os
import logging
import hashlib
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import json

from config import config

logger = logging.getLogger(__name__)


class SecurityManager:
    """Manager for security-related operations."""
    
    def __init__(self):
        self.security_dir = config.DATA_DIR / "security"
        self.security_dir.mkdir(parents=True, exist_ok=True)
        
        # Encryption key storage
        self.key_file = self.security_dir / "encryption.key"
        self.salt_file = self.security_dir / "salt.key"
        
        # Initialize or load encryption key
        self.fernet = self._get_or_create_encryption_key()
        
        # Audit log
        self.audit_log_file = config.DATA_DIR / "audit.log"
        
        # Session management
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.session_timeout = timedelta(hours=24)
    
    def _get_or_create_encryption_key(self) -> Fernet:
        """Get or create encryption key."""
        if self.key_file.exists() and self.salt_file.exists():
            try:
                with open(self.key_file, 'rb') as f:
                    key = f.read()
                with open(self.salt_file, 'rb') as f:
                    salt = f.read()
                
                # Derive key from password
                password = os.getenv("ENCRYPTION_PASSWORD", "default_health_bot_password").encode()
                kdf = PBKDF2HMAC(
                    algorithm=hashes.SHA256(),
                    length=32,
                    salt=salt,
                    iterations=100000,
                )
                key = base64.urlsafe_b64encode(kdf.derive(password))
                return Fernet(key)
            except Exception as e:
                logger.error(f"Error loading encryption key: {e}")
                return self._create_new_encryption_key()
        else:
            return self._create_new_encryption_key()
    
    def _create_new_encryption_key(self) -> Fernet:
        """Create new encryption key."""
        try:
            # Generate salt
            salt = os.urandom(16)
            
            # Derive key from password
            password = os.getenv("ENCRYPTION_PASSWORD", "default_health_bot_password").encode()
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(password))
            
            # Save files
            with open(self.salt_file, 'wb') as f:
                f.write(salt)
            with open(self.key_file, 'wb') as f:
                f.write(key)
            
            # Set restrictive permissions (Unix only)
            try:
                os.chmod(self.key_file, 0o600)
                os.chmod(self.salt_file, 0o600)
            except:
                pass  # Windows doesn't support Unix permissions
            
            logger.info("Created new encryption key")
            return Fernet(key)
            
        except Exception as e:
            logger.error(f"Error creating encryption key: {e}")
            # Fallback to insecure Fernet (for development only)
            return Fernet(Fernet.generate_key())
    
    def encrypt_sensitive_data(self, data: Dict[str, Any]) -> str:
        """
        Encrypt sensitive data.
        
        Args:
            data: Dictionary with sensitive data
        
        Returns:
            Encrypted base64 string
        """
        try:
            json_data = json.dumps(data).encode()
            encrypted = self.fernet.encrypt(json_data)
            return base64.b64encode(encrypted).decode()
        except Exception as e:
            logger.error(f"Encryption error: {e}")
            return ""
    
    def decrypt_sensitive_data(self, encrypted_data: str) -> Optional[Dict[str, Any]]:
        """
        Decrypt sensitive data.
        
        Args:
            encrypted_data: Encrypted base64 string
        
        Returns:
            Decrypted dictionary or None
        """
        try:
            decoded = base64.b64decode(encrypted_data.encode())
            decrypted = self.fernet.decrypt(decoded)
            return json.loads(decrypted.decode())
        except Exception as e:
            logger.error(f"Decryption error: {e}")
            return None
    
    def hash_telegram_id(self, telegram_id: str) -> str:
        """
        Hash Telegram ID for anonymous storage.
        
        Args:
            telegram_id: Raw Telegram ID
        
        Returns:
            Hashed ID
        """
        salt = os.getenv("TELEGRAM_SALT", "health_bot_salt").encode()
        return hashlib.sha256(f"{telegram_id}".encode() + salt).hexdigest()
    
    def generate_session_token(self, telegram_id: str) -> str:
        """
        Generate secure session token.
        
        Args:
            telegram_id: User's Telegram ID
        
        Returns:
            Session token
        """
        token = secrets.token_urlsafe(32)
        
        self.sessions[token] = {
            "telegram_id": telegram_id,
            "created_at": datetime.now(),
            "last_activity": datetime.now()
        }
        
        # Clean old sessions
        self._cleanup_sessions()
        
        return token
    
    def validate_session_token(self, token: str) -> Optional[str]:
        """
        Validate session token and return Telegram ID.
        
        Args:
            token: Session token
        
        Returns:
            Telegram ID if valid, None otherwise
        """
        if token not in self.sessions:
            return None
        
        session = self.sessions[token]
        
        # Check timeout
        if datetime.now() - session["last_activity"] > self.session_timeout:
            del self.sessions[token]
            return None
        
        # Update last activity
        session["last_activity"] = datetime.now()
        
        return session["telegram_id"]
    
    def invalidate_session(self, token: str):
        """Invalidate session token."""
        if token in self.sessions:
            del self.sessions[token]
    
    def _cleanup_sessions(self):
        """Remove expired sessions."""
        expired = [
            token for token, session in self.sessions.items()
            if datetime.now() - session["last_activity"] > self.session_timeout
        ]
        
        for token in expired:
            del self.sessions[token]
    
    def log_audit_event(
        self,
        event_type: str,
        telegram_id: str,
        details: Dict[str, Any],
        ip_address: str = None
    ):
        """
        Log audit event for security tracking.
        
        Args:
            event_type: Type of event (login, data_access, settings_change, etc.)
            telegram_id: User's Telegram ID
            details: Event details
            ip_address: Optional IP address
        """
        audit_entry = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "telegram_id_hash": self.hash_telegram_id(telegram_id),
            "details": details,
            "ip_address": ip_address
        }
        
        try:
            with open(self.audit_log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(audit_entry, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"Audit log error: {e}")
    
    def sanitize_input(self, text: str, max_length: int = 1000) -> str:
        """
        Sanitize user input.
        
        Args:
            text: Raw input text
            max_length: Maximum allowed length
        
        Returns:
            Sanitized text
        """
        if not text:
            return ""
        
        # Truncate
        text = text[:max_length]
        
        # Remove potentially dangerous characters
        dangerous_chars = ['<', '>', '"', "'", '\\', '\x00', '\x1a']
        for char in dangerous_chars:
            text = text.replace(char, '')
        
        return text.strip()
    
    def validate_api_key(self, api_key: str, expected_prefix: str = "") -> bool:
        """
        Validate API key format.
        
        Args:
            api_key: API key to validate
            expected_prefix: Expected prefix (optional)
        
        Returns:
            True if valid format
        """
        if not api_key or len(api_key) < 16:
            return False
        
        if expected_prefix and not api_key.startswith(expected_prefix):
            return False
        
        # Check for reasonable entropy
        unique_chars = len(set(api_key))
        if unique_chars < 8:
            return False
        
        return True
    
    def get_security_report(self) -> Dict[str, Any]:
        """Get security status report."""
        return {
            "encryption_enabled": self.fernet is not None,
            "active_sessions": len(self.sessions),
            "audit_log_exists": self.audit_log_file.exists(),
            "audit_log_size": self.audit_log_file.stat().st_size if self.audit_log_file.exists() else 0,
            "security_dir": str(self.security_dir)
        }


class PrivacyManager:
    """Manager for privacy-related operations."""
    
    def __init__(self):
        self.consent_file = config.DATA_DIR / "consents.json"
        self.consents: Dict[str, Dict[str, Any]] = self._load_consents()
    
    def _load_consents(self) -> Dict[str, Dict[str, Any]]:
        """Load user consents from file."""
        if self.consent_file.exists():
            try:
                with open(self.consent_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return {}
    
    def _save_consents(self):
        """Save consents to file."""
        try:
            with open(self.consent_file, 'w', encoding='utf-8') as f:
                json.dump(self.consents, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving consents: {e}")
    
    def give_consent(
        self,
        telegram_id: str,
        consent_type: str,
        granted: bool = True
    ):
        """
        Record user consent.
        
        Args:
            telegram_id: User's Telegram ID
            consent_type: Type of consent (data_collection, ai_analysis, etc.)
            granted: Whether consent was granted
        """
        if telegram_id not in self.consents:
            self.consents[telegram_id] = {}
        
        self.consents[telegram_id][consent_type] = {
            "granted": granted,
            "timestamp": datetime.now().isoformat(),
            "version": "1.0"
        }
        
        self._save_consents()
        
        logger.info(f"Consent {consent_type} {'granted' if granted else 'denied'} by user {telegram_id}")
    
    def check_consent(self, telegram_id: str, consent_type: str) -> bool:
        """
        Check if user has given consent.
        
        Args:
            telegram_id: User's Telegram ID
            consent_type: Type of consent to check
        
        Returns:
            True if consent granted
        """
        if telegram_id not in self.consents:
            return False
        
        consent = self.consents[telegram_id].get(consent_type)
        if not consent:
            return False
        
        return consent.get("granted", False)
    
    def revoke_all_consents(self, telegram_id: str):
        """
        Revoke all consents for a user (GDPR right to be forgotten).
        
        Args:
            telegram_id: User's Telegram ID
        """
        if telegram_id in self.consents:
            del self.consents[telegram_id]
            self._save_consents()
            logger.info(f"All consents revoked for user {telegram_id}")
    
    def get_privacy_policy(self) -> str:
        """Get privacy policy text."""
        return """
🔒 <b>Политика конфиденциальности</b>

1. <b>Сбор данных</b>
Мы собираем только необходимые данные:
- Telegram ID для идентификации
- Данные о здоровье и питании (по вашему желанию)
- Настройки и предпочтения

2. <b>Хранение данных</b>
- Все данные хранятся локально
- Чувствительные данные шифруются
- Доступ третьим лицам исключен

3. <b>Использование данных</b>
- Анализ питания и тренировок
- Персонализированные рекомендации
- Генерация отчетов

4. <b>Ваши права</b>
- Доступ к вашим данным
- Исправление данных
- Удаление всех данных (право на забвение)

5. <b>Безопасность</b>
- Шифрование чувствительных данных
- Регулярное резервное копирование
- Аудит доступа к данным

Используя бота, вы соглашаетесь с этой политикой.
"""
    
    def get_data_export(self, telegram_id: str, user_data: Dict[str, Any]) -> str:
        """
        Export all user data (GDPR data portability).
        
        Args:
            telegram_id: User's Telegram ID
            user_data: User's data dictionary
        
        Returns:
            JSON string with all user data
        """
        export_data = {
            "telegram_id": telegram_id,
            "export_date": datetime.now().isoformat(),
            "data": user_data,
            "consents": self.consents.get(telegram_id, {})
        }
        
        return json.dumps(export_data, ensure_ascii=False, indent=2)


# Setup security logging
def setup_security_logging():
    """Set up dedicated security logging."""
    security_logger = logging.getLogger("security")
    security_logger.setLevel(logging.INFO)
    
    # Security log file
    security_log_file = config.DATA_DIR / "security.log"
    
    handler = logging.FileHandler(security_log_file, encoding='utf-8')
    handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    ))
    
    security_logger.addHandler(handler)
    
    return security_logger


# Global instances
security_manager = SecurityManager()
privacy_manager = PrivacyManager()
security_logger = setup_security_logging()
