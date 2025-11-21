"""
Image processing utilities including face recognition
"""
import base64
from pathlib import Path
from typing import List, Optional, Tuple
import face_recognition
import numpy as np
from PIL import Image
from config import Config
from utils.logger import logger


class ImageProcessor:
    """Handle image downloads and face recognition"""
    
    def __init__(self):
        self.faces_dir = Config.FACES_DIR
        self.id_cards_dir = Config.ID_CARDS_DIR
        self.similarity_threshold = Config.FACE_SIMILARITY_THRESHOLD
    
    def save_image(self, image_data: bytes, filename: str, image_type: str = 'face') -> str:
        """
        Save image to local storage
        
        Args:
            image_data: Image binary data
            filename: Filename to save as
            image_type: Type of image ('face' or 'id_card')
        
        Returns:
            Path to saved image
        """
        try:
            if image_type == 'face':
                save_path = self.faces_dir / filename
            else:
                save_path = self.id_cards_dir / filename
            
            with open(save_path, 'wb') as f:
                f.write(image_data)
            
            logger.info(f"Saved {image_type} image: {save_path}")
            return str(save_path)
        
        except Exception as e:
            logger.error(f"Failed to save image: {e}")
            return ""
    
    def image_to_base64(self, image_path: str) -> str:
        """
        Convert image file to base64 string
        
        Args:
            image_path: Path to image file
        
        Returns:
            Base64 encoded string
        """
        try:
            with open(image_path, 'rb') as f:
                image_data = f.read()
            return base64.b64encode(image_data).decode('utf-8')
        
        except Exception as e:
            logger.error(f"Failed to convert image to base64: {e}")
            return ""
    
    def get_face_encoding(self, image_path: str) -> Optional[np.ndarray]:
        """
        Extract face encoding from image
        
        Args:
            image_path: Path to image file
        
        Returns:
            Face encoding array or None if no face found
        """
        try:
            # Load image
            image = face_recognition.load_image_file(image_path)
            
            # Get face encodings
            encodings = face_recognition.face_encodings(image)
            
            if len(encodings) == 0:
                logger.warning(f"No face detected in image: {image_path}")
                return None
            
            if len(encodings) > 1:
                logger.warning(f"Multiple faces detected in image: {image_path}, using first one")
            
            return encodings[0]
        
        except Exception as e:
            logger.error(f"Failed to extract face encoding: {e}")
            return None
    
    def compare_faces(
        self,
        face_encoding: np.ndarray,
        known_encodings: List[np.ndarray]
    ) -> Tuple[bool, float]:
        """
        Compare face encoding against known encodings
        
        Args:
            face_encoding: Face encoding to compare
            known_encodings: List of known face encodings
        
        Returns:
            Tuple of (is_match, best_similarity_score)
        """
        if not known_encodings:
            return False, 0.0
        
        try:
            # Calculate face distances
            face_distances = face_recognition.face_distance(known_encodings, face_encoding)
            
            # Get best match
            best_match_index = np.argmin(face_distances)
            best_distance = face_distances[best_match_index]
            
            # Convert distance to similarity (1 - distance)
            similarity = 1 - best_distance
            
            # Check if match exceeds threshold
            is_match = similarity >= self.similarity_threshold
            
            return is_match, similarity
        
        except Exception as e:
            logger.error(f"Failed to compare faces: {e}")
            return False, 0.0
    
    def find_duplicate_faces(
        self,
        new_face_path: str,
        existing_faces: List[str]
    ) -> List[Tuple[str, float]]:
        """
        Find potential duplicate faces in database
        
        Args:
            new_face_path: Path to new face image
            existing_faces: List of paths to existing face images
        
        Returns:
            List of tuples (face_path, similarity_score) for matches above threshold
        """
        try:
            # Get encoding for new face
            new_encoding = self.get_face_encoding(new_face_path)
            if new_encoding is None:
                logger.warning(f"Could not extract face from new image: {new_face_path}")
                return []
            
            matches = []
            
            # Compare against each existing face
            for existing_path in existing_faces:
                existing_encoding = self.get_face_encoding(existing_path)
                if existing_encoding is None:
                    continue
                
                is_match, similarity = self.compare_faces(
                    new_encoding,
                    [existing_encoding]
                )
                
                if is_match:
                    matches.append((existing_path, similarity))
                    logger.warning(
                        f"Potential duplicate detected: {new_face_path} "
                        f"matches {existing_path} (similarity: {similarity:.2f})"
                    )
            
            # Sort by similarity descending
            matches.sort(key=lambda x: x[1], reverse=True)
            
            return matches
        
        except Exception as e:
            logger.error(f"Error finding duplicate faces: {e}")
            return []
    
    def validate_image(self, image_path: str) -> bool:
        """
        Validate that image is readable and contains a face
        
        Args:
            image_path: Path to image file
        
        Returns:
            True if valid, False otherwise
        """
        try:
            # Try to open with PIL
            img = Image.open(image_path)
            img.verify()
            
            # Check if face is detectable
            encoding = self.get_face_encoding(image_path)
            
            return encoding is not None
        
        except Exception as e:
            logger.error(f"Image validation failed: {e}")
            return False
