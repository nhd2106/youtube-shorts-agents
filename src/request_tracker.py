import uuid
import time
from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
import threading
import json

class RequestStatus(Enum):
    PENDING = "pending"
    GENERATING_CONTENT = "generating_content"
    GENERATING_AUDIO = "generating_audio"
    GENERATING_IMAGES = "generating_images"
    WAITING_FOR_IMAGE_SELECTION = "waiting_for_image_selection"
    GENERATING_VIDEO = "generating_video"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class RequestData:
    request_id: str
    status: RequestStatus
    progress: int
    result: Optional[Dict[str, Any]]
    error: Optional[str]
    created_at: float
    updated_at: float

class RequestTracker:
    def __init__(self):
        self._requests: Dict[str, RequestData] = {}
        self._lock = threading.Lock()
    
    def create_request(self) -> str:
        """Create a new request and return its ID"""
        request_id = str(uuid.uuid4())
        self._requests[request_id] = {
            'status': 'pending',
            'progress': 0,
            'result': None,
            'error': None,
            'created_at': time.time(),
            'updated_at': time.time()
        }
        return request_id
    
    def get_request(self, request_id: str) -> Optional[RequestData]:
        """Get request data by ID"""
        with self._lock:
            request_data = self._requests.get(request_id)
            if request_data:
                print(f"Found request {request_id} with status {request_data.status}")
            else:
                print(f"Request {request_id} not found. Available requests: {list(self._requests.keys())}")
            return request_data
    
    def update_request(self, request_id: str, **kwargs) -> None:
        """Update request data"""
        if request_id not in self._requests:
            raise KeyError(f"Request {request_id} not found")
        
        self._requests[request_id].update({
            **kwargs,
            'updated_at': time.time()
        })
    
    def clean_old_requests(self, max_age_hours: int = 24) -> None:
        """Remove requests older than max_age_hours"""
        with self._lock:
            current_time = time.time()
            max_age_seconds = max_age_hours * 3600
            
            old_requests = [
                req_id for req_id, data in self._requests.items()
                if current_time - data.created_at > max_age_seconds
            ]
            
            for req_id in old_requests:
                del self._requests[req_id]
                print(f"Cleaned up old request {req_id}")
    
    def get_all_requests(self) -> Dict[str, RequestData]:
        """Get all requests (for debugging)"""
        with self._lock:
            return self._requests.copy()
