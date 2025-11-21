"""
Data sanitization utilities for protecting sensitive information
"""
import re
from typing import Any, Dict, List

class DataSanitizer:
    """Sanitize sensitive data from logs and displays"""
    
    # Patterns to identify sensitive data
    SENSITIVE_KEYS = [
        'password', 'secret', 'token', 'key', 'bearer', 'authorization',
        'x-api-key', 'x-ca-key', 'x-ca-signature', 'api_key', 'app_secret'
    ]
    
    SENSITIVE_PATTERNS = [
        (r'\d{10}', '***IDNUM***'),  # National ID numbers (10 digits)
        (r'\d{14}', '***IDNUM***'),  # Extended ID numbers (14 digits)
        (r'05\d{8}', '***PHONE***'),  # Saudi phone numbers
        (r'\+9665\d{8}', '***PHONE***'),  # Saudi phone numbers with country code
    ]
    
    @staticmethod
    def sanitize(data: Any, depth: int = 0) -> Any:
        """
        Recursively sanitize sensitive data
        
        Args:
            data: Data to sanitize (dict, list, str, etc.)
            depth: Current recursion depth (to prevent infinite loops)
        
        Returns:
            Sanitized data
        """
        if depth > 10:  # Prevent infinite recursion
            return '[MAX_DEPTH_REACHED]'
        
        if isinstance(data, dict):
            return DataSanitizer._sanitize_dict(data, depth)
        elif isinstance(data, list):
            return DataSanitizer._sanitize_list(data, depth)
        elif isinstance(data, str):
            return DataSanitizer._sanitize_string(data)
        else:
            return data
    
    @staticmethod
    def _sanitize_dict(data: Dict, depth: int) -> Dict:
        """Sanitize dictionary"""
        sanitized = {}
        
        for key, value in data.items():
            # Check if key is sensitive
            is_sensitive = any(
                sensitive.lower() in key.lower()
                for sensitive in DataSanitizer.SENSITIVE_KEYS
            )
            
            if is_sensitive:
                # Completely redact sensitive values
                if isinstance(value, str) and value:
                    sanitized[key] = '***REDACTED***'
                else:
                    sanitized[key] = '***REDACTED***'
            else:
                # Recursively sanitize nested structures
                sanitized[key] = DataSanitizer.sanitize(value, depth + 1)
        
        return sanitized
    
    @staticmethod
    def _sanitize_list(data: List, depth: int) -> List:
        """Sanitize list"""
        return [DataSanitizer.sanitize(item, depth + 1) for item in data]
    
    @staticmethod
    def _sanitize_string(data: str) -> str:
        """Sanitize string by replacing sensitive patterns"""
        result = data
        
        for pattern, replacement in DataSanitizer.SENSITIVE_PATTERNS:
            result = re.sub(pattern, replacement, result)
        
        return result
    
    @staticmethod
    def sanitize_headers(headers: Dict) -> Dict:
        """Specifically sanitize HTTP headers"""
        return DataSanitizer.sanitize(dict(headers))
    
    @staticmethod
    def sanitize_body(body: Any) -> Any:
        """Specifically sanitize request/response body"""
        return DataSanitizer.sanitize(body)
    
    @staticmethod
    def redact_base64_images(data: Any) -> Any:
        """Replace base64 encoded images with placeholder"""
        if isinstance(data, dict):
            result = {}
            for key, value in data.items():
                if key in ['faceData', 'imageData', 'cardImage'] and isinstance(value, str):
                    # Check if it looks like base64
                    if len(value) > 100:
                        result[key] = f'[BASE64_IMAGE_{len(value)}_BYTES]'
                    else:
                        result[key] = value
                elif isinstance(value, (dict, list)):
                    result[key] = DataSanitizer.redact_base64_images(value)
                else:
                    result[key] = value
            return result
        elif isinstance(data, list):
            return [DataSanitizer.redact_base64_images(item) for item in data]
        else:
            return data
