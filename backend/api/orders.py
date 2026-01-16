from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text 
from core.database import get_db
from models.order import Order, OrderStatus
from models.schemas import OrderInput, OrderStatusUpdate, CleanOrder
from services.llm_cleaner import clean_order
from utils.broadcast import broadcast_kitchen, broadcast_dashboard
from core.redis_client import push_order_to_queue, get_active_table_order, set_active_table_order,remove_active_table_order
import json
from sqlalchemy import func
from models.order import Order
from datetime import date

router = APIRouter()

@router.post("/orders/raw")
async def process_raw_order(input_data: OrderInput, db: Session = Depends(get_db)):
    """WhatsApp webhook endpoint"""
    
    # Clean with LLM pipeline
    cleaning_result = await clean_order(input_data.raw_text)
    
    if not cleaning_result["success"]:
        return {
            "success": False,
            "error": cleaning_result["error"],
            "whatsapp_reply": f"Please add Table#: {cleaning_result['suggestion']}"
        }
    
    clean_order_data = cleaning_result["order"]
    
    # Check if table has active order (add items)
    active_order_id = get_active_table_order(clean_order_data["table_num"])
    if active_order_id:
        # Update existing order
        order = db.query(Order).filter(Order.id == int(active_order_id)).first()
        if order and order.status not in [OrderStatus.COMPLETED, OrderStatus.CANCELLED]:
            # Add items to existing order
            existing_items = json.loads(order.items)
            new_items = clean_order_data["items"]
            order.items = json.dumps(existing_items + new_items)
            order.total_amount += clean_order_data["total_amount"]
            order.raw_text += f" | {input_data.raw_text}"
            db.commit()
            order_id = order.id
        else:
            order_id = None
            active_order_id = None
    if not active_order_id:
        # Create new order
        db_order = Order(
            table_num=clean_order_data["table_num"],
            items=json.dumps(clean_order_data["items"]),
            total_amount=float(clean_order_data["total_amount"]),
            raw_text=input_data.raw_text,
            status=OrderStatus.NEW
        )
        db.add(db_order)
        db.commit()
        db.refresh(db_order)
        order_id = db_order.id
        set_active_table_order(db_order.table_num, str(order_id))
    
    # Broadcast to kitchen and dashboard
    order_data = {
        "id": order_id,
        "table_num": clean_order_data["table_num"],
        "items": clean_order_data["items"],
        "total_amount": clean_order_data["total_amount"],
        "status": "new"
    }
    
    broadcast_kitchen("new_order", order_data)
    broadcast_dashboard("revenue_update", {
        "revenue": calculate_daily_revenue(db),
        "active_tables": len(db.query(Order).filter(Order.status != OrderStatus.SERVED).all())
    })
    
    return {"success": True, "order_id": order_id, "order": order_data}

@router.get("/orders/pending")
def get_pending_orders(db: Session = Depends(get_db)):
    """Kitchen display endpoint"""
    orders = db.query(Order).filter(
        Order.status.in_([OrderStatus.NEW, OrderStatus.COOKING])
    ).order_by(Order.cleaned_at).all()
    return orders

@router.patch("/orders/{order_id}/status")
def update_order_status(order_id: int, status_update: OrderStatusUpdate, db: Session = Depends(get_db)):
    """Kitchen status updates"""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    order.status = OrderStatus(status_update.status)
    db.commit()
    if order.status == OrderStatus.COMPLETED:
        remove_active_table_order(order.table_num)
    # Broadcast status change
    broadcast_kitchen("status_update", {
        "order_id": order_id,
        "status": status_update.status
    })
    broadcast_dashboard("order_status_update", {
        "order_id": order_id,
        "status": status_update.status
    })
    
    return {"success": True, "order_id": order_id, "new_status": status_update.status}

def calculate_daily_revenue(db: Session) -> float:
    """Pure ORM - No raw SQL"""
    today = date.today()
    result = db.query(func.coalesce(func.sum(Order.total_amount), 0)) \
               .filter(func.date(Order.cleaned_at) == today) \
               .scalar()
    return float(result)


@router.post("/orders/whatsapp")
async def whatsapp_webhook(request: dict, db: Session = Depends(get_db)):
    """WhatsApp Business API webhook"""
    raw_text = await parse_whatsapp_webhook(request)
    if not raw_text:
        return {"status": "ignored"}
    
    phone_number = request["entry"][0]["changes"][0]["value"]["contacts"][0]["wa_id"]
    
    # Process through LLM pipeline
    cleaning_result = await clean_order(raw_text)
    
    if cleaning_result["success"]:
        # Save order (same logic as /orders/raw)
        # ... existing save logic ...
        await broadcast_kitchen("new_order", order_data)
        return {"status": "order_processed"}
    else:
        # Reply to waiter
        reply_msg = f"❌ {cleaning_result['error']}\n📝 {cleaning_result['suggestion']}"
        await send_whatsapp_reply(phone_number, reply_msg)
        return {"status": "error_replied"}
