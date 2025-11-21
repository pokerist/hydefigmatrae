"""
Configuration management for HydePark sync system
"""
from pathlib import Path

class Config:
    """Application configuration"""
    
    # Supabase Configuration
    SUPABASE_BASE_URL = 'https://xrkxxqhoglrimiljfnml.supabase.co/functions/v1/make-server-2c3121a9'
    SUPABASE_API_KEY = 'XyZ9k2LmN4pQ7rS8tU0vW1xA3bC5dE6f7gH8iJ9kL0mN1o=='
    SUPABASE_AUTH_BEARER = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inhya3h4cWhvZ2xyaW1pbGpmbm1sIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjI0MjIxMDEsImV4cCI6MjA3Nzk5ODEwMX0.3G20OL9ujCPyFOOMYc6UVbIv97v5LjsWbQLPZaqHRsk'
    
    # HikCentral Configuration
    HIKCENTRAL_BASE_URL = 'https://10.127.0.2/artemis'
    HIKCENTRAL_APP_KEY = '22452825'
    HIKCENTRAL_APP_SECRET = 'Q9bWogAziordVdIngfoa'
    HIKCENTRAL_USER_ID = 'admin'
    HIKCENTRAL_ORG_INDEX_CODE = '1'
    HIKCENTRAL_PRIVILEGE_GROUP_ID = '3'
    HIKCENTRAL_VERIFY_SSL = False
    
    # Dashboard Configuration
    DASHBOARD_HOST = '0.0.0.0'
    DASHBOARD_PORT = 8080
    DASHBOARD_USERNAME = 'admin'
    DASHBOARD_PASSWORD = '123456'
    DASHBOARD_SESSION_TIMEOUT = 1800
    DASHBOARD_LOG_RETENTION_DAYS = 30
    
    # Logging Configuration
    LOG_API_REQUESTS = True
    MAX_REQUEST_LOGS = 10000
    
    # System Configuration
    SYNC_INTERVAL_SECONDS = 60
    DATA_DIR = Path('./data')
    FACE_SIMILARITY_THRESHOLD = 0.4
    
    # Data directories
    FACES_DIR = DATA_DIR / 'faces'
    ID_CARDS_DIR = DATA_DIR / 'id_cards'
    WORKERS_DB = DATA_DIR / 'workers.json'
    REQUEST_LOGS_DB = DATA_DIR / 'request_logs.json'
    
    # Secret key for Flask sessions
    SECRET_KEY = 'hydepark-dashboard-secret-key-2025'
    
    @classmethod
    def ensure_directories(cls):
        """Ensure all required directories exist"""
        cls.DATA_DIR.mkdir(exist_ok=True)
        cls.FACES_DIR.mkdir(exist_ok=True)
        cls.ID_CARDS_DIR.mkdir(exist_ok=True)
        
        # Create database files if they don't exist
        if not cls.WORKERS_DB.exists():
            cls.WORKERS_DB.write_text('[]')
        
        if not cls.REQUEST_LOGS_DB.exists():
            cls.REQUEST_LOGS_DB.write_text('[]')
    
    @classmethod
    def validate(cls):
        """Validate required configuration"""
        errors = []
        
        if not cls.SUPABASE_BASE_URL:
            errors.append("SUPABASE_BASE_URL is required")
        
        if not cls.SUPABASE_API_KEY and not cls.SUPABASE_AUTH_BEARER:
            errors.append("Either SUPABASE_API_KEY or SUPABASE_AUTH_BEARER is required")
        
        if not cls.HIKCENTRAL_BASE_URL:
            errors.append("HIKCENTRAL_BASE_URL is required")
        
        if not cls.HIKCENTRAL_APP_KEY:
            errors.append("HIKCENTRAL_APP_KEY is required")
        
        if not cls.HIKCENTRAL_APP_SECRET:
            errors.append("HIKCENTRAL_APP_SECRET is required")
        
        if errors:
            raise ValueError("Configuration errors:\n" + "\n".join(f"  - {e}" for e in errors))
        
        return True
