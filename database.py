"""
Local database operations using JSON files
"""
import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from config import Config

class Database:
    """Thread-safe JSON database for local storage"""
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.lock = threading.Lock()
        self._ensure_db_exists()
    
    def _ensure_db_exists(self):
        """Create database file if it doesn't exist"""
        if not self.db_path.exists():
            with self.lock:
                self.db_path.write_text(json.dumps([], indent=2))
    
    def read(self) -> List[Dict]:
        """Read all records from database"""
        with self.lock:
            try:
                return json.loads(self.db_path.read_text())
            except Exception as e:
                print(f"Error reading database: {e}")
                return []
    
    def write(self, data: List[Dict]):
        """Write all records to database"""
        with self.lock:
            try:
                self.db_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
            except Exception as e:
                print(f"Error writing database: {e}")
    
    def find_one(self, query: Dict) -> Optional[Dict]:
        """Find first record matching query"""
        data = self.read()
        for record in data:
            if all(record.get(k) == v for k, v in query.items()):
                return record
        return None
    
    def find_many(self, query: Dict = None) -> List[Dict]:
        """Find all records matching query"""
        data = self.read()
        if query is None:
            return data
        
        results = []
        for record in data:
            if all(record.get(k) == v for k, v in query.items()):
                results.append(record)
        return results
    
    def insert(self, record: Dict) -> Dict:
        """Insert a new record"""
        data = self.read()
        record['_created_at'] = datetime.utcnow().isoformat()
        record['_updated_at'] = datetime.utcnow().isoformat()
        data.append(record)
        self.write(data)
        return record
    
    def update(self, query: Dict, update: Dict) -> int:
        """Update records matching query"""
        data = self.read()
        updated_count = 0
        
        for record in data:
            if all(record.get(k) == v for k, v in query.items()):
                record.update(update)
                record['_updated_at'] = datetime.utcnow().isoformat()
                updated_count += 1
        
        if updated_count > 0:
            self.write(data)
        
        return updated_count
    
    def delete(self, query: Dict) -> int:
        """Delete records matching query"""
        data = self.read()
        original_count = len(data)
        
        data = [
            record for record in data
            if not all(record.get(k) == v for k, v in query.items())
        ]
        
        deleted_count = original_count - len(data)
        if deleted_count > 0:
            self.write(data)
        
        return deleted_count


class WorkersDatabase(Database):
    """Database for worker records"""
    
    def __init__(self):
        super().__init__(Config.WORKERS_DB)
    
    def get_by_national_id(self, national_id: str) -> Optional[Dict]:
        """Get worker by national ID"""
        return self.find_one({'nationalIdNumber': national_id})
    
    def get_by_worker_id(self, worker_id: str) -> Optional[Dict]:
        """Get worker by worker ID"""
        return self.find_one({'workerId': worker_id})
    
    def upsert_worker(self, worker_data: Dict) -> Dict:
        """Insert or update worker"""
        existing = self.get_by_national_id(worker_data['nationalIdNumber'])
        
        if existing:
            self.update(
                {'nationalIdNumber': worker_data['nationalIdNumber']},
                worker_data
            )
            return {**existing, **worker_data}
        else:
            return self.insert(worker_data)
    
    def get_all_workers(self) -> List[Dict]:
        """Get all workers"""
        return self.read()
    
    def get_workers_by_status(self, status: str) -> List[Dict]:
        """Get workers by status"""
        return self.find_many({'status': status})


class RequestLogsDatabase(Database):
    """Database for API request logs"""
    
    def __init__(self):
        super().__init__(Config.REQUEST_LOGS_DB)
    
    def add_log(self, log_data: Dict) -> Dict:
        """Add a new request log"""
        # Clean up old logs if exceeding max
        logs = self.read()
        if len(logs) >= Config.MAX_REQUEST_LOGS:
            # Keep only the most recent logs
            logs = logs[-(Config.MAX_REQUEST_LOGS - 1):]
            self.write(logs)
        
        return self.insert(log_data)
    
    def get_recent_logs(self, limit: int = 100, filters: Dict = None) -> List[Dict]:
        """Get recent logs with optional filtering"""
        logs = self.read()
        
        # Apply filters
        if filters:
            filtered_logs = []
            for log in logs:
                match = True
                
                # Filter by API target
                if filters.get('api_target') and log.get('api_target') != filters['api_target']:
                    match = False
                
                # Filter by success status
                if filters.get('success') is not None:
                    log_success = 200 <= log.get('status_code', 500) < 300
                    if log_success != filters['success']:
                        match = False
                
                # Filter by date range
                if filters.get('start_date'):
                    log_time = datetime.fromisoformat(log.get('timestamp', ''))
                    if log_time < datetime.fromisoformat(filters['start_date']):
                        match = False
                
                if filters.get('end_date'):
                    log_time = datetime.fromisoformat(log.get('timestamp', ''))
                    if log_time > datetime.fromisoformat(filters['end_date']):
                        match = False
                
                # Filter by endpoint
                if filters.get('endpoint') and filters['endpoint'].lower() not in log.get('endpoint', '').lower():
                    match = False
                
                if match:
                    filtered_logs.append(log)
            
            logs = filtered_logs
        
        # Sort by timestamp descending and limit
        logs = sorted(logs, key=lambda x: x.get('timestamp', ''), reverse=True)
        return logs[:limit]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about request logs"""
        logs = self.read()
        
        if not logs:
            return {
                'total_requests': 0,
                'success_rate': 0,
                'avg_duration': 0,
                'failed_requests': 0
            }
        
        successful = sum(1 for log in logs if 200 <= log.get('status_code', 500) < 300)
        total = len(logs)
        durations = [log.get('duration_ms', 0) for log in logs if log.get('duration_ms')]
        
        return {
            'total_requests': total,
            'success_rate': (successful / total * 100) if total > 0 else 0,
            'avg_duration': sum(durations) / len(durations) if durations else 0,
            'failed_requests': total - successful
        }
    
    def cleanup_old_logs(self):
        """Remove logs older than retention period"""
        logs = self.read()
        cutoff_date = datetime.utcnow().timestamp() - (Config.DASHBOARD_LOG_RETENTION_DAYS * 86400)
        
        cleaned_logs = [
            log for log in logs
            if datetime.fromisoformat(log.get('timestamp', '')).timestamp() > cutoff_date
        ]
        
        if len(cleaned_logs) < len(logs):
            self.write(cleaned_logs)
            print(f"Cleaned up {len(logs) - len(cleaned_logs)} old logs")
