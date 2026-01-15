from typing import Dict, Any
import json

# Global connection managers
kitchen_connections = []
dashboard_connections = []

async def broadcast_kitchen(event: str, data: Dict[str, Any]):
    """Broadcast to all kitchen WebSocket clients"""
    message = json.dumps({"event": event, "data": data})
    for i, conn in enumerate(kitchen_connections[:]):
        try:
            await conn.send_text(message)
        except:
            kitchen_connections.pop(i)

async def broadcast_dashboard(event: str, data: Dict[str, Any]):
    """Broadcast to dashboard clients"""
    message = json.dumps({"event": event, "data": data})
    for i, conn in enumerate(dashboard_connections[:]):
        try:
            await conn.send_text(message)
        except:
            dashboard_connections.pop(i)
