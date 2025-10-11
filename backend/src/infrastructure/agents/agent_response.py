from typing import Tuple, Union

class AgentResponse:
    def __init__(self, success: bool, data: str, error_message: str = None):
        self.success = success
        self.data = data
        self.error_message = error_message
    
    @classmethod
    def success_response(cls, data: str):
        return cls(success=True, data=data)
    
    @classmethod
    def error_response(cls, error_message: str):
        return cls(success=False, data="", error_message=error_message)