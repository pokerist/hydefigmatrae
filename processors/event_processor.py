"""
Event processing logic for worker synchronization
"""
from datetime import datetime, timedelta
from typing import Dict, List
from pathlib import Path
from api.supabase_api import SupabaseAPI
from api.hikcentral_api import HikCentralAPI
from database import WorkersDatabase
from processors.image_processor import ImageProcessor
from utils.logger import logger


class EventProcessor:
    """Process events from online application and sync with HikCentral"""
    
    def __init__(self):
        self.supabase = SupabaseAPI()
        self.hikcentral = HikCentralAPI()
        self.workers_db = WorkersDatabase()
        self.image_processor = ImageProcessor()
    
    def process_events(self):
        """Main processing loop - fetch and process pending events"""
        try:
            logger.info("Fetching pending events...")
            events = self.supabase.get_pending_events()
            
            if not events:
                logger.info("No pending events to process")
                return
            
            logger.info(f"Processing {len(events)} events")
            
            for event in events:
                self.process_single_event(event)
        
        except Exception as e:
            logger.error(f"Error processing events: {e}")
    
    def process_single_event(self, event: Dict):
        """
        Process a single event
        
        Args:
            event: Event object from API
        """
        event_type = event.get('type')
        event_id = event.get('id', 'unknown')
        
        logger.info(f"Processing event: {event_type} (ID: {event_id})")
        
        try:
            if event_type == 'worker.created':
                # Handle both formats:
                # 1. {"type": "worker.created", "data": {...}}
                # 2. {"type": "worker.created", "workers": [{...}]}
                workers = event.get('workers', [])
                event_data = event.get('data', {})
                
                if workers:
                    logger.info(f"Processing {len(workers)} workers from event")
                    for worker in workers:
                        self.handle_worker_created(worker)
                elif event_data:
                    self.handle_worker_created(event_data)
                else:
                    logger.error(f"No worker data found in event {event_id}")
            
            elif event_type == 'workers.bulk_created':
                workers = event.get('data', {}).get('workers', [])
                if not workers:
                    workers = event.get('workers', [])
                
                logger.info(f"Processing {len(workers)} workers in bulk")
                for worker in workers:
                    self.handle_worker_created(worker)
            
            elif event_type == 'worker.blocked':
                workers = event.get('workers', [])
                event_data = event.get('data', {})
                
                if workers:
                    for worker in workers:
                        self.handle_worker_blocked(worker)
                elif event_data:
                    self.handle_worker_blocked(event_data)
            
            elif event_type == 'unit.workers_blocked':
                workers = event.get('data', {}).get('workers', [])
                if not workers:
                    workers = event.get('workers', [])
                
                for worker in workers:
                    self.handle_worker_blocked(worker)
            
            elif event_type == 'worker.deleted' or \
                 event_type == 'user.expired_workers_deleted' or \
                 event_type == 'user.deleted_workers_deleted':
                workers = event.get('workers', [])
                event_data = event.get('data', {})
                
                if workers:
                    for worker in workers:
                        self.handle_worker_deleted(worker)
                elif event_data:
                    self.handle_worker_deleted(event_data)
            
            elif event_type == 'worker.unblocked':
                workers = event.get('workers', [])
                event_data = event.get('data', {})
                
                if workers:
                    for worker in workers:
                        self.handle_worker_unblocked(worker)
                elif event_data:
                    self.handle_worker_unblocked(event_data)
            
            elif event_type == 'unit.workers_unblocked':
                workers = event.get('data', {}).get('workers', [])
                if not workers:
                    workers = event.get('workers', [])
                
                for worker in workers:
                    self.handle_worker_unblocked(worker)
            
            else:
                logger.warning(f"Unknown event type: {event_type}")
        
        except Exception as e:
            logger.error(f"Error processing event {event_type} (ID: {event_id}): {e}", exc_info=True)
    
    def handle_worker_created(self, worker_data: Dict):
        """Handle worker creation event"""
        try:
            national_id = worker_data.get('nationalIdNumber')
            worker_id = worker_data.get('workerId') or worker_data.get('id')
            
            if not national_id:
                logger.error(f"No national ID in worker data: {worker_data}")
                return
            
            if not worker_id:
                logger.error(f"No worker ID in worker data: {worker_data}")
                return
            
            logger.info(f"Creating worker: {national_id} (Worker ID: {worker_id})")
            
            # Check for existing worker
            existing = self.workers_db.get_by_national_id(national_id)
            if existing and existing.get('hikcentral_person_id'):
                logger.info(f"Worker already exists in HikCentral: {national_id}")
                return
            
            # Download images
            face_url = worker_data.get('facePhoto') or worker_data.get('facePhotoUrl')
            id_card_url = worker_data.get('nationalIdImage') or worker_data.get('idCardImageUrl')
            
            if not face_url:
                logger.error(f"No face photo URL for worker: {national_id}")
                return
            
            logger.info(f"Downloading images for worker: {national_id}")
            
            # Save images locally
            face_filename = f"{national_id}_face.jpg"
            id_card_filename = f"{national_id}_id.jpg"
            
            face_path = str(Path(self.image_processor.faces_dir) / face_filename)
            id_card_path = str(Path(self.image_processor.id_cards_dir) / id_card_filename)
            
            if not self.supabase.download_image(face_url, face_path):
                logger.error(f"Failed to download face photo for worker: {national_id}")
                return
            
            logger.info(f"Face photo downloaded: {face_path}")
            
            if id_card_url:
                if self.supabase.download_image(id_card_url, id_card_path):
                    logger.info(f"ID card downloaded: {id_card_path}")
                else:
                    logger.warning(f"Failed to download ID card for worker: {national_id}")
            
            # Check for duplicate faces
            logger.info(f"Checking for duplicate faces for worker: {national_id}")
            existing_workers = self.workers_db.get_all_workers()
            existing_face_paths = [
                w.get('face_image_path')
                for w in existing_workers
                if w.get('face_image_path') and Path(w['face_image_path']).exists()
            ]
            
            duplicates = self.image_processor.find_duplicate_faces(face_path, existing_face_paths)
            
            if duplicates:
                logger.warning(
                    f"Potential duplicate faces found for worker {national_id}. "
                    f"Top match: {duplicates[0][0]} (similarity: {duplicates[0][1]:.2f})"
                )
                # Block worker due to potential fraud
                self.supabase.update_worker_status(
                    worker_id=worker_id,
                    national_id_number=national_id,
                    status='blocked',
                    blocked_reason=f'وجه مطابق لعامل آخر - احتمال تزوير (تشابه: {duplicates[0][1]:.1%})'
                )
                return
            
            logger.info(f"No duplicate faces found for worker: {national_id}")
            
            # Convert face image to base64
            logger.info(f"Converting face image to base64 for worker: {national_id}")
            face_base64 = self.image_processor.image_to_base64(face_path)
            if not face_base64:
                logger.error(f"Failed to convert face image to base64: {national_id}")
                return
            
            # Prepare dates from Supabase data
            from datetime import datetime
            
            # Get validFrom and validTo from worker data (format: "2025-11-21")
            valid_from = worker_data.get('validFrom')
            valid_to = worker_data.get('validTo')
            
            if valid_from and valid_to:
                # Parse dates: "2025-11-21" -> "2025-11-21T00:00:00+02:00"
                try:
                    from_dt = datetime.strptime(valid_from, '%Y-%m-%d')
                    to_dt = datetime.strptime(valid_to, '%Y-%m-%d')
                    
                    # Set time to start of day for validFrom, end of day for validTo
                    begin_time = from_dt.strftime('%Y-%m-%dT00:00:00') + '+02:00'
                    end_time = to_dt.strftime('%Y-%m-%dT23:59:59') + '+02:00'
                    
                    logger.info(f"Using validFrom/validTo dates: {valid_from} to {valid_to}")
                except Exception as e:
                    logger.warning(f"Error parsing validFrom/validTo dates: {e}. Using createdAt fallback.")
                    valid_from = None
                    valid_to = None
            
            # Fallback: use createdAt if validFrom/validTo not available
            if not valid_from or not valid_to:
                created_at = worker_data.get('createdAt')
                
                if created_at:
                    # Parse ISO date: 2025-11-20T21:12:40.643Z
                    # Convert to HikCentral format: 2025-11-20T21:12:40+02:00
                    dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    # Convert to Cairo timezone (+02:00)
                    begin_time = dt.strftime('%Y-%m-%dT%H:%M:%S') + '+02:00'
                    # Add 10 years
                    from datetime import timedelta
                    end_dt = dt + timedelta(days=3650)
                    end_time = end_dt.strftime('%Y-%m-%dT%H:%M:%S') + '+02:00'
                else:
                    # Fallback to now if no createdAt
                    now = datetime.now()
                    begin_time = now.strftime('%Y-%m-%dT%H:%M:%S') + '+02:00'
                    end_time = (now + timedelta(days=3650)).strftime('%Y-%m-%dT%H:%M:%S') + '+02:00'
            
            # Split name into family and given names
            full_name = worker_data.get('fullName', '')
            name_parts = full_name.split(' ', 1)
            family_name = name_parts[0] if name_parts else ''
            given_name = name_parts[1] if len(name_parts) > 1 else ''
            
            # Use previously resolved worker_id
            
            # Add person to HikCentral
            logger.info(f"Adding person to HikCentral: {national_id} (Worker ID: {worker_id})")
            logger.info(f"Date range: {begin_time} to {end_time}")
            person_id = self.hikcentral.add_person(
                person_code=worker_id,  # Use worker.id from Supabase (e.g., "25165168156010")
                family_name=family_name,
                given_name=given_name,
                gender=1,  # Male by default
                phone_no=worker_data.get('phoneNumber', ''),
                email=worker_data.get('email', ''),
                face_data=face_base64,
                begin_time=begin_time,
                end_time=end_time
            )
            
            logger.info(f"HikCentral add_person returned: {person_id}")
            
            if not person_id:
                logger.error(f"Failed to add person to HikCentral: {national_id}")
                # Still save to local database with pending status
                logger.info(f"Saving worker to local database with pending status: {national_id}")
                self.workers_db.upsert_worker({
                    'workerId': worker_id,
                    'nationalIdNumber': national_id,
                    'fullName': full_name,
                    'phoneNumber': worker_data.get('phoneNumber', ''),
                    'email': worker_data.get('email', ''),
                    'status': 'pending',
                    'hikcentral_person_id': '',
                    'face_image_path': face_path,
                    'id_card_image_path': id_card_path if id_card_url else '',
                    'has_privilege_access': False,
                    'created_at': datetime.utcnow().isoformat()
                })
                logger.info(f"Worker saved to local database: {national_id}")
                return
            
            logger.info(f"Person added to HikCentral with ID: {person_id}")
            
            # Add to privilege group (grant access)
            logger.info(f"Adding person to privilege group: {national_id}")
            privilege_result = self.hikcentral.add_to_privilege_group(person_id)
            logger.info(f"Privilege group result: {privilege_result}")
            
            if not privilege_result:
                logger.warning(f"Failed to add person to privilege group: {national_id}")
            else:
                logger.info(f"Person added to privilege group: {national_id}")
            
            # Update local database
            logger.info(f"Updating local database for worker: {national_id}")
            worker_record = {
                'workerId': worker_id,
                'nationalIdNumber': national_id,
                'fullName': full_name,
                'phoneNumber': worker_data.get('phoneNumber', ''),
                'email': worker_data.get('email', ''),
                'status': 'approved',
                'hikcentral_person_id': person_id,
                'face_image_path': face_path,
                'id_card_image_path': id_card_path if id_card_url else '',
                'has_privilege_access': True,
                'created_at': datetime.utcnow().isoformat()
            }
            logger.info(f"Worker record prepared: {worker_record}")
            
            self.workers_db.upsert_worker(worker_record)
            logger.info(f"Worker saved to local database successfully: {national_id}")
            
            # Update status in online application
            logger.info(f"Updating worker status in Supabase: {national_id}")
            self.supabase.update_worker_status(
                worker_id=worker_id,
                national_id_number=national_id,
                status='approved',
                external_id=person_id
            )
            
            logger.info(f"✓ Successfully created worker in HikCentral: {national_id} (Person ID: {person_id})")
        
        except Exception as e:
            logger.error(f"Error handling worker creation: {e}", exc_info=True)
    
    def handle_worker_blocked(self, worker_data: Dict):
        """Handle worker blocking event"""
        try:
            national_id = worker_data.get('nationalIdNumber')
            worker_id = worker_data.get('id')
            blocked_reason = worker_data.get('blockedReason', 'تم الحظر بواسطة النظام')
            
            logger.info(f"Blocking worker: {national_id}")
            
            # Get worker from local database
            worker = self.workers_db.get_by_national_id(national_id)
            if not worker:
                logger.warning(f"Worker not found in local database: {national_id}")
                return
            
            person_id = worker.get('hikcentral_person_id')
            if not person_id:
                logger.warning(f"No HikCentral person ID for worker: {national_id}")
                return
            
            # Remove from privilege group (revoke access)
            if self.hikcentral.remove_from_privilege_group(person_id):
                # Update local database
                self.workers_db.update(
                    {'nationalIdNumber': national_id},
                    {
                        'status': 'blocked',
                        'blockedReason': blocked_reason,
                        'has_privilege_access': False,
                        'blocked_at': datetime.utcnow().isoformat()
                    }
                )
                
                logger.info(f"Successfully blocked worker: {national_id}")
            else:
                logger.error(f"Failed to block worker in HikCentral: {national_id}")
        
        except Exception as e:
            logger.error(f"Error handling worker blocking: {e}")
    
    def handle_worker_deleted(self, worker_data: Dict):
        """Handle worker deletion event"""
        try:
            national_id = worker_data.get('nationalIdNumber')
            
            logger.info(f"Deleting worker: {national_id}")
            
            # Get worker from local database
            worker = self.workers_db.get_by_national_id(national_id)
            if not worker:
                logger.warning(f"Worker not found in local database: {national_id}")
                return
            
            person_id = worker.get('hikcentral_person_id')
            if not person_id:
                logger.warning(f"No HikCentral person ID for worker: {national_id}")
                return
            
            # Delete from HikCentral
            if self.hikcentral.delete_person(person_id):
                # Update local database (mark as deleted but keep history)
                self.workers_db.update(
                    {'nationalIdNumber': national_id},
                    {
                        'status': 'deleted',
                        'deleted_at': datetime.utcnow().isoformat()
                    }
                )
                
                logger.info(f"Successfully deleted worker: {national_id}")
            else:
                logger.error(f"Failed to delete worker from HikCentral: {national_id}")
        
        except Exception as e:
            logger.error(f"Error handling worker deletion: {e}")
    
    def handle_worker_unblocked(self, worker_data: Dict):
        """Handle worker unblocking event"""
        try:
            national_id = worker_data.get('nationalIdNumber')
            worker_id = worker_data.get('id')
            
            logger.info(f"Unblocking worker: {national_id}")
            
            # Get worker from local database
            worker = self.workers_db.get_by_national_id(national_id)
            if not worker:
                logger.warning(f"Worker not found in local database: {national_id}")
                return
            
            person_id = worker.get('hikcentral_person_id')
            if not person_id:
                logger.warning(f"No HikCentral person ID for worker: {national_id}")
                return
            
            # Add back to privilege group (restore access)
            if self.hikcentral.add_to_privilege_group(person_id):
                # Update local database
                self.workers_db.update(
                    {'nationalIdNumber': national_id},
                    {
                        'status': 'approved',
                        'blockedReason': '',
                        'has_privilege_access': True,
                        'unblocked_at': datetime.utcnow().isoformat()
                    }
                )
                
                # Update status in online application
                self.supabase.update_worker_status(
                    worker_id=worker_id,
                    national_id_number=national_id,
                    status='approved',
                    external_id=person_id
                )
                
                logger.info(f"Successfully unblocked worker: {national_id}")
            else:
                logger.error(f"Failed to unblock worker in HikCentral: {national_id}")
        
        except Exception as e:
            logger.error(f"Error handling worker unblocking: {e}")