import uuid
import time
from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

class RequestStatus(Enum):
    PENDING = "pending"
    GENERATING_CONTENT = "generating_content"
    GENERATING_AUDIO = "generating_audio"
    GENERATING_IMAGES = "generating_images"
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
    
    def create_request(self) -> str:
        """Create a new request and return its ID"""
        request_id = str(uuid.uuid4())
        self._requests[request_id] = RequestData(
            request_id=request_id,
            status=RequestStatus.PENDING,
            progress=0,
            result=None,
            error=None,
            created_at=time.time(),
            updated_at=time.time()
        )
        return request_id
    
    def update_request(
        self,
        request_id: str,
        status: Optional[RequestStatus] = None,
        progress: Optional[int] = None,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ) -> None:
        """Update request status and data"""
        if request_id not in self._requests:
            raise ValueError(f"Request {request_id} not found")
        
        request = self._requests[request_id]
        
        if status:
            request.status = status
        if progress is not None:
            request.progress = progress
        if result:
            request.result = result
        if error:
            request.error = error
            request.status = RequestStatus.FAILED
        
        request.updated_at = time.time()
    
    def get_request(self, request_id: str) -> Optional[Dict[str, Any]]:
        """Get request status and data"""
        if request_id not in self._requests:
            return None
        
        request = self._requests[request_id]
        return {
            "request_id": request.request_id,
            "status": request.status.value,
            "progress": request.progress,
            "result": request.result,
            "error": request.error,
            "created_at": request.created_at,
            "updated_at": request.updated_at
        }
    
    def clean_old_requests(self, max_age_hours: int = 24) -> None:
        """Clean up requests older than max_age_hours"""
        current_time = time.time()
        max_age = max_age_hours * 3600
        
        old_requests = [
            req_id for req_id, req in self._requests.items()
            if current_time - req.created_at > max_age
        ]
        
        for req_id in old_requests:
            del self._requests[req_id]
