from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session
from core.database import get_db
from models.order import Order, OrderStatus
from utils.broadcast import broadcast_kitchen, broadcast_dashboard, kitchen_connections, dashboard_connections
import json

router = APIRouter()

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

kitchen_manager = ConnectionManager()
dashboard_manager = ConnectionManager()

@router.websocket("/ws/kitchen")
async def websocket_kitchen(websocket: WebSocket):
    global kitchen_connections
    await kitchen_manager.connect(websocket)
    kitchen_connections.append(websocket)
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        kitchen_manager.disconnect(websocket)
        kitchen_connections.remove(websocket)

@router.websocket("/ws/dashboard")
async def websocket_dashboard(websocket: WebSocket):
    global dashboard_connections
    await dashboard_manager.connect(websocket)
    dashboard_connections.append(websocket)
    
    # Send initial metrics snapshot
    await broadcast_dashboard("initial_metrics", {
        "revenue_today": 12500,
        "orders_count": 42,
        "active_tables": 5
    })
    
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        dashboard_manager.disconnect(websocket)
        dashboard_connections.remove(websocket)

@router.get("/ws/kitchen/orders")
async def get_kitchen_orders(db: Session = Depends(get_db)):
    """Fallback for kitchen page load"""
    orders = db.query(Order).filter(
        Order.status.in_([OrderStatus.NEW, OrderStatus.COOKING])
    ).order_by(Order.cleaned_at).all()
    return [{"id": o.id, "table_num": o.table_num, "items": o.items, "total_amount": o.total_amount, "status": o.status.value} for o in orders]
