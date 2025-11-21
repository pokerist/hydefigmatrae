"""
Enhanced logging system with API request tracking
"""
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, Optional
from database import RequestLogsDatabase
from utils.sanitizer import DataSanitizer

# Configure standard logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('hydepark-sync.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger('hydepark-sync')


class RequestLogger:
    """Logger for API requests with sanitization"""
    
    def __init__(self):
        self.db = RequestLogsDatabase()
        self.sanitizer = DataSanitizer()
    
    def log_request(
        self,
        api_target: str,
        endpoint: str,
        method: str,
        headers: Dict,
        body: Any,
        start_time: float,
        end_time: float,
        status_code: int,
        response_body: Any,
        error: Optional[str] = None
    ):
        """
        Log an API request with sanitization
        
        Args:
            api_target: Target API (supabase/hikcentral)
            endpoint: API endpoint URL
            method: HTTP method
            headers: Request headers
            body: Request body
            start_time: Request start timestamp
            end_time: Request end timestamp
            status_code: HTTP status code
            response_body: Response body
            error: Error message if request failed
        """
        try:
            # Calculate duration
            duration_ms = int((end_time - start_time) * 1000)
            
            # Sanitize data
            sanitized_headers = self.sanitizer.sanitize_headers(headers)
            sanitized_body = self.sanitizer.sanitize_body(body)
            sanitized_body = self.sanitizer.redact_base64_images(sanitized_body)
            sanitized_response = self.sanitizer.sanitize_body(response_body)
            sanitized_response = self.sanitizer.redact_base64_images(sanitized_response)
            
            # Create log record
            log_record = {
                'id': str(uuid.uuid4()),
                'timestamp': datetime.utcnow().isoformat(),
                'api_target': api_target,
                'endpoint': endpoint,
                'method': method,
                'headers': sanitized_headers,
                'body': sanitized_body,
                'status_code': status_code,
                'response_body': sanitized_response,
                'duration_ms': duration_ms,
                'error': error,
                'success': 200 <= status_code < 300
            }
            
            # Store in database
            self.db.add_log(log_record)
            
            # Also log to standard logger
            if error:
                logger.error(f"{api_target.upper()} {method} {endpoint} - {status_code} - {duration_ms}ms - ERROR: {error}")
            else:
                logger.info(f"{api_target.upper()} {method} {endpoint} - {status_code} - {duration_ms}ms")
        
        except Exception as e:
            logger.error(f"Error logging request: {e}")
    
    def get_recent_logs(self, limit: int = 100, filters: Dict = None) -> list:
        """Get recent request logs"""
        return self.db.get_recent_logs(limit, filters)
    
    def get_stats(self) -> Dict:
        """Get request statistics"""
        return self.db.get_stats()
    
    def cleanup_old_logs(self):
        """Clean up old logs based on retention policy"""
        self.db.cleanup_old_logs()


# Global request logger instance
request_logger = RequestLogger()
