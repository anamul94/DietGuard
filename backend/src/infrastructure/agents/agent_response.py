from typing import Tuple, Union, Optional, Dict, Any

class AgentResponse:
    def __init__(self, success: bool, data: str, error_message: str = None, metadata: Optional[Dict[str, Any]] = None):
        self.success = success
        self.data = data
        self.error_message = error_message
        self.metadata = metadata or {}
    
    @classmethod
    def success_response(cls, data: str, metadata: Optional[Dict[str, Any]] = None):
        return cls(success=True, data=data, metadata=metadata)
    
    @classmethod
    def error_response(cls, error_message: str):
        return cls(success=False, data="", error_message=error_message)