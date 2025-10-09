import socketio
from typing import Dict, Any

# Create Socket.IO server
sio = socketio.AsyncServer(cors_allowed_origins="*")

class SocketManager:
    @staticmethod
    async def emit_food_event(event_data: str):
        try:
            await sio.emit('food_analysis_complete', event_data)
        except Exception as e:
            print(f"WebSocket emit error: {e}")

socket_manager = SocketManager()