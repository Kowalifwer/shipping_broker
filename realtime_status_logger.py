from fastapi import WebSocket
from fastapi.websockets import WebSocketDisconnect
import asyncio
from fastapi.routing import APIRouter
from typing import List, Optional, Dict, overload, Union
from datetime import datetime
# Create a router and add the endpoints
router = APIRouter()

# WebSocket endpoint to handle the communication
class WebSocketManager:
    def __init__(self):
        self.connections: Dict[str, WebSocket] = {}  # Use a dictionary to store connections with identifiers

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        self.connections[user_id] = websocket

    @overload
    def disconnect(self, input: WebSocket) -> None:
        ...

    @overload
    def disconnect(self, input: str):
        ...

    def disconnect(self, input: Union[WebSocket, str]):
        if isinstance(input, WebSocket):
            websocket = input
            for user_id, connection in dict(self.connections).items():
                if connection == websocket:
                    del self.connections[user_id]

        elif isinstance(input, str):
            user_id = input
            if user_id in dict(self.connections):
                del self.connections[user_id]

        else:
            raise Exception("Invalid input type")

    async def disconnect_all(self):
        print("disconnecting all sockets")
        for connection in self.connections.values():
            await connection.close()
        self.connections = {}

    async def send_update(self, user_id: str, message: str):
        if user_id in self.connections:
            await self.connections[user_id].send_text(message)
    
    async def send_update_json(self, user_id: str, json_data: dict):
        if user_id in self.connections:
            await self.connections[user_id].send_json(json_data)

websocket_manager = WebSocketManager()

class LiveLogger:
    """Class to handle live logging of status updates to a channel"""
    def __init__(self, websocket_manager: WebSocketManager, channels: List[str] = []):
        self.websocket_manager = websocket_manager
        self.channels = channels
        #generate a random user id
        self.user_id = "1" #TODO: in future if dealing with multiple users, generate a random user id
    
    async def report_to_channel(self, channel: str, message: str):
        if channel not in self.channels:
            raise Exception("Reporting to a channel that is not registered. Please register the channel first in the LiveLogger.channels list.")

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        await self.websocket_manager.send_update_json(
            self.user_id,
            {channel: f"{timestamp}: {message}"}
        )
    
    async def report_to_all_channels(self, message: str):
        for channel in self.channels:
            await self.report_to_channel(channel, message)
    
    async def close_session(self):
        await self.websocket_manager.disconnect_all()

@router.websocket("/ws/info/{user_id}/")
async def websocket_endpoint(websocket: WebSocket, user_id: str):

    await websocket_manager.connect(websocket, user_id)
    try:
        while True:
            # A way to keep the websocket alive, whilst also checking for disconnectino (WebSocketDisconnect)
            await websocket.receive_text()

    except WebSocketDisconnect:
        websocket_manager.disconnect(websocket)

    except Exception as e:
        print(f"Exception occured in websocket_endpoint process for socket {websocket}: {e}")