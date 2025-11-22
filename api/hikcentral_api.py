"""
HikCentral API client with AK/SK authentication
"""
import time
import hmac
import hashlib
import base64
import uuid
import json
from datetime import datetime, timezone
from urllib.parse import urlparse
import requests
from typing import Dict, Optional
from config import Config
from utils.logger import request_logger, logger


class HikCentralAPI:
    """Client for HikCentral API interactions with AK/SK authentication"""
    
    def __init__(self):
        # Clean base URL - remove any trailing path
        base_url = Config.HIKCENTRAL_BASE_URL
        # If base_url ends with /artemis or similar, strip it
        # We want just https://IP:PORT
        if base_url:
            from urllib.parse import urlparse
            parsed = urlparse(base_url)
            # Rebuild URL without path
            self.base_url = f"{parsed.scheme}://{parsed.netloc}"
        else:
            self.base_url = base_url
            
        self.app_key = Config.HIKCENTRAL_APP_KEY
        self.app_secret = Config.HIKCENTRAL_APP_SECRET
        self.user_id = Config.HIKCENTRAL_USER_ID
        self.org_index_code = Config.HIKCENTRAL_ORG_INDEX_CODE
        self.privilege_group_id = Config.HIKCENTRAL_PRIVILEGE_GROUP_ID
        self.verify_ssl = Config.HIKCENTRAL_VERIFY_SSL
    
    def _generate_signature(
        self,
        method: str,
        uri: str,
        headers: Dict,
        body: str = ""
    ) -> str:
        """
        Generate HMAC-SHA256 signature for request
        
        Args:
            method: HTTP method
            uri: Request URI (path from base URL)
            headers: Request headers
            body: Request body string
        
        Returns:
            Base64-encoded signature
        """
        # Build string to sign according to HikCentral spec
        parts = [
            method,
            headers.get('Accept', 'application/json')
        ]
        
        # Add Content-MD5 if present in headers
        if 'Content-MD5' in headers:
            parts.append(headers['Content-MD5'])
        
        # Content-Type
        parts.append(headers.get('Content-Type', 'application/json;charset=UTF-8'))
        
        # Custom headers (x-ca-*) - MUST be in alphabetical order and lowercase
        parts.append(f"x-ca-key:{headers.get('x-ca-key', headers.get('X-Ca-Key'))}")
        parts.append(f"x-ca-nonce:{headers.get('x-ca-nonce', headers.get('X-Ca-Nonce'))}")
        parts.append(f"x-ca-timestamp:{headers.get('x-ca-timestamp', headers.get('X-Ca-Timestamp'))}")
        
        # URI
        parts.append(uri)
        
        string_to_sign = '\n'.join(parts)
        
        # Log for debugging
        logger.info(f"String to sign:\n{string_to_sign}")
        
        # Generate HMAC-SHA256 signature
        signature = hmac.new(
            self.app_secret.encode('utf-8'),
            string_to_sign.encode('utf-8'),
            hashlib.sha256
        ).digest()
        
        return base64.b64encode(signature).decode('utf-8')
    
    def _get_content_md5(self, body: str) -> str:
        """Calculate Content-MD5 header value"""
        md5_hash = hashlib.md5(body.encode('utf-8')).digest()
        return base64.b64encode(md5_hash).decode('utf-8')
    
    def _get_authenticated_headers(self, body: Optional[str] = None) -> Dict:
        """
        Generate authenticated headers for HikCentral request
        
        Args:
            body: Request body as JSON string
        
        Returns:
            Dictionary of headers with authentication
        """
        nonce = str(uuid.uuid4())
        timestamp = str(int(time.time() * 1000))
        
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json;charset=UTF-8',
            'X-Ca-Key': self.app_key,
            'X-Ca-Nonce': nonce,
            'X-Ca-Timestamp': timestamp,
            'X-Ca-Signature-Headers': 'x-ca-key,x-ca-nonce,x-ca-timestamp',
            'userId': self.user_id
        }
        
        # Add Content-MD5 only if body exists
        if body:
            headers['Content-MD5'] = self._get_content_md5(body)
        
        return headers
    
    def _make_request(
        self,
        endpoint: str,
        body: Dict,
        method: str = 'POST'
    ) -> Optional[Dict]:
        """
        Make authenticated request to HikCentral API
        
        Args:
            endpoint: API endpoint path (full path including base path like /artemis/api/...)
            body: Request body
            method: HTTP method
        
        Returns:
            Response data or None on error
        """
        url = f"{self.base_url}{endpoint}"
        body_str = json.dumps(body, ensure_ascii=True, separators=(",", ":")) if body else ""
        
        headers = self._get_authenticated_headers(body_str if body else None)
        
        # URI for signature is the full endpoint path
        # The endpoint already includes the base path (e.g., /artemis/api/...)
        uri = endpoint
        
        # Generate signature
        signature = self._generate_signature(
            method,
            uri,
            headers,
            body_str if body else ""
        )
        headers['X-Ca-Signature'] = signature
        
        # Log headers being sent (for debugging)
        logger.info(f"Headers being sent to HikCentral: {headers}")
        
        start_time = time.time()
        error = None
        response_body = None
        status_code = 500
        
        try:
            response = requests.post(
                url,
                headers=headers,
                data=body_str,
                verify=self.verify_ssl,
                timeout=30
            )
            
            status_code = response.status_code
            response_body = response.json() if response.text else None
            
            # Check HikCentral response code
            if response_body and response_body.get('code') != '0':
                error = f"HikCentral error: {response_body.get('msg', 'Unknown error')}"
                logger.error(error)
                return None
            
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
            logger.error(f"HikCentral API error: {error}")
            return None
        
        finally:
            end_time = time.time()
            
            # Log request
            if Config.LOG_API_REQUESTS:
                request_logger.log_request(
                    api_target='hikcentral',
                    endpoint=url,
                    method=method,
                    headers=headers,
                    body=body,
                    start_time=start_time,
                    end_time=end_time,
                    status_code=status_code,
                    response_body=response_body,
                    error=error
                )
    
    def add_person(
        self,
        person_code: str,
        family_name: str,
        given_name: str,
        gender: int,
        phone_no: str,
        email: str,
        face_data: str,
        begin_time: str,
        end_time: str
    ) -> Optional[str]:
        """
        Add person to HikCentral
        
        Returns:
            Person ID if successful, None otherwise
        """
        body = {
            'personCode': person_code,
            'personFamilyName': family_name,
            'personGivenName': given_name,
            'gender': gender,
            'orgIndexCode': self.org_index_code,
            'phoneNo': phone_no,
            'email': email or '',
            'faces': [{'faceData': face_data}],
            'fingerPrint': [],
            'cards': [],
            'beginTime': begin_time,
            'endTime': end_time,
            'residentRoomNo': 1,
            'residentFloorNo': 1
        }
        
        result = self._make_request('/artemis/api/resource/v1/person/single/add', body)

        if not result:
            logger.error(f"Failed to add person: {person_code}")
            return None

        data = result.get('data') if isinstance(result, dict) else None
        if isinstance(data, dict):
            person_id = data.get('personId') or data.get('id') or person_code
            logger.info(f"Successfully added person: {person_code} (ID: {person_id})")
            return person_id

        logger.error(f"Failed to parse HikCentral response for person: {person_code}")
        return None
    
    def update_person(
        self,
        person_id: str,
        person_code: str,
        family_name: str,
        given_name: str,
        gender: int,
        phone_no: str,
        email: str,
        begin_time: str,
        end_time: str
    ) -> bool:
        """Update person in HikCentral"""
        body = {
            'personId': person_id,
            'personCode': person_code,
            'personFamilyName': family_name,
            'personGivenName': given_name,
            'orgIndexCode': self.org_index_code,
            'gender': gender,
            'phoneNo': phone_no,
            'email': email or '',
            'cards': [],
            'beginTime': begin_time,
            'endTime': end_time,
            'residentRoomNo': 1,
            'residentFloorNo': 1,
            'remark': ''
        }
        
        result = self._make_request('/artemis/api/resource/v1/person/single/update', body)
        
        if result and result.get('code') == '0':
            logger.info(f"Successfully updated person: {person_id}")
            return True
        else:
            logger.error(f"Failed to update person: {person_id}")
            return False
    
    def delete_person(self, person_id: str) -> bool:
        """Delete person from HikCentral"""
        body = {'personId': person_id}
        
        result = self._make_request('/artemis/api/resource/v1/person/single/delete', body)
        
        if result and result.get('code') == '0':
            logger.info(f"Successfully deleted person: {person_id}")
            return True
        else:
            logger.error(f"Failed to delete person: {person_id}")
            return False
    
    def add_to_privilege_group(self, person_id: str) -> bool:
        """Add person to privilege group (grant access)"""
        body = {
            'privilegeGroupId': self.privilege_group_id,
            'type': 1,
            'list': [{'id': person_id}]
        }
        
        result = self._make_request('/artemis/api/acs/v1/privilege/group/single/addPersons', body)
        
        if result and result.get('code') == '0':
            logger.info(f"Successfully added person to privilege group: {person_id}")
            return True
        else:
            logger.error(f"Failed to add person to privilege group: {person_id}")
            return False
    
    def remove_from_privilege_group(self, person_id: str) -> bool:
        """Remove person from privilege group (revoke access)"""
        body = {
            'privilegeGroupId': self.privilege_group_id,
            'type': 1,
            'list': [{'id': person_id}]
        }
        
        result = self._make_request('/artemis/api/acs/v1/privilege/group/single/deletePersons', body)
        
        if result and result.get('code') == '0':
            logger.info(f"Successfully removed person from privilege group: {person_id}")
            return True
        else:
            logger.error(f"Failed to remove person from privilege group: {person_id}")
            return False