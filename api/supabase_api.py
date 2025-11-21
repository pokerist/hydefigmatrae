"""
Supabase API client for online application integration
"""
import time
import requests
from typing import Dict, List, Optional
from config import Config
from utils.logger import request_logger, logger


class SupabaseAPI:
    """Client for Supabase API interactions"""
    
    def __init__(self):
        self.base_url = Config.SUPABASE_BASE_URL
        self.api_key = Config.SUPABASE_API_KEY
        self.bearer_token = Config.SUPABASE_AUTH_BEARER
    
    def _get_headers(self) -> Dict:
        """Get request headers with authentication"""
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        # Supabase Edge Functions require BOTH Bearer token AND API key
        if self.bearer_token:
            headers['Authorization'] = f'Bearer {self.bearer_token}'
        
        if self.api_key:
            headers['X-API-Key'] = self.api_key
        
        return headers
    
    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None
    ) -> Optional[Dict]:
        """
        Make HTTP request with logging
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            data: Request body data
            params: Query parameters
        
        Returns:
            Response data or None on error
        """
        url = f"{self.base_url}{endpoint}"
        headers = self._get_headers()
        
        start_time = time.time()
        error = None
        response_body = None
        status_code = 500
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, params=params, timeout=30)
            elif method == 'POST':
                response = requests.post(url, headers=headers, json=data, params=params, timeout=30)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            status_code = response.status_code
            response_body = response.json() if response.text else None
            
            response.raise_for_status()
            
            return response_body
        
        except requests.exceptions.RequestException as e:
            error = str(e)
            if hasattr(e, 'response') and e.response is not None:
                status_code = e.response.status_code
                try:
                    response_body = e.response.json()
                except:
                    response_body = e.response.text
            logger.error(f"Supabase API error: {error}")
            return None
        
        finally:
            end_time = time.time()
            
            # Log request
            if Config.LOG_API_REQUESTS:
                request_logger.log_request(
                    api_target='supabase',
                    endpoint=url,
                    method=method,
                    headers=headers,
                    body=data or params,
                    start_time=start_time,
                    end_time=end_time,
                    status_code=status_code,
                    response_body=response_body,
                    error=error
                )
    
    def get_pending_events(self, limit: int = 100, event_type: Optional[str] = None) -> List[Dict]:
        """
        Fetch pending events from online application
        
        Args:
            limit: Maximum number of events to fetch
            event_type: Optional filter by event type
        
        Returns:
            List of event objects
        """
        params = {'limit': limit}
        if event_type:
            params['type'] = event_type
        
        result = self._make_request('GET', '/admin/events/pending', params=params)
        
        if result and isinstance(result, list):
            logger.info(f"Fetched {len(result)} pending events")
            return result
        elif result and 'events' in result:
            logger.info(f"Fetched {len(result['events'])} pending events")
            return result['events']
        else:
            logger.warning("No events returned from API")
            return []
    
    def get_events_stats(self) -> Optional[Dict]:
        """Get statistics on pending/consumed events"""
        return self._make_request('GET', '/admin/events/stats')
    
    def update_worker_status(
        self,
        worker_id: Optional[str] = None,
        national_id_number: Optional[str] = None,
        status: str = 'approved',
        external_id: Optional[str] = None,
        blocked_reason: Optional[str] = None
    ) -> bool:
        """
        Update worker status in online application
        
        Args:
            worker_id: Worker UUID
            national_id_number: National ID number (alternative to worker_id)
            status: Worker status ('approved' or 'blocked')
            external_id: External system ID (HikCentral person ID)
            blocked_reason: Reason for blocking (required if status is 'blocked')
        
        Returns:
            True if update successful, False otherwise
        """
        if not worker_id and not national_id_number:
            logger.error("Either worker_id or national_id_number must be provided")
            return False
        
        if status not in ['approved', 'blocked']:
            logger.error(f"Invalid status: {status}")
            return False
        
        if status == 'blocked' and not blocked_reason:
            logger.error("blocked_reason is required when status is 'blocked'")
            return False
        
        data = {'status': status}
        
        if worker_id:
            data['workerId'] = worker_id
        if national_id_number:
            data['nationalIdNumber'] = national_id_number
        if external_id:
            data['externalId'] = external_id
        if blocked_reason:
            data['blockedReason'] = blocked_reason
        
        result = self._make_request('POST', '/admin/workers/update-status', data=data)
        
        if result:
            logger.info(f"Successfully updated worker status to {status}")
            return True
        else:
            logger.error(f"Failed to update worker status")
            return False
    
    def download_image(self, url: str, save_path: str) -> bool:
        """
        Download image from URL
        
        Args:
            url: Image URL
            save_path: Local path to save image
        
        Returns:
            True if download successful, False otherwise
        """
        start_time = time.time()
        error = None
        status_code = 500
        
        try:
            response = requests.get(url, timeout=30)
            status_code = response.status_code
            response.raise_for_status()
            
            with open(save_path, 'wb') as f:
                f.write(response.content)
            
            logger.info(f"Downloaded image to {save_path}")
            return True
        
        except Exception as e:
            error = str(e)
            logger.error(f"Failed to download image: {error}")
            return False
        
        finally:
            end_time = time.time()
            
            # Log request
            if Config.LOG_API_REQUESTS:
                request_logger.log_request(
                    api_target='supabase',
                    endpoint=url,
                    method='GET',
                    headers={},
                    body=None,
                    start_time=start_time,
                    end_time=end_time,
                    status_code=status_code,
                    response_body=f"Image download to {save_path}",
                    error=error
                )