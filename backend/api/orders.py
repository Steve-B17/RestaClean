from fastapi import APIRouter,Form, Depends, HTTPException
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
from twilio.rest import Client
import os
from dotenv import load_dotenv
load_dotenv()
router = APIRouter()
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")
client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)



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


@router.post("/whatsapp")
async def whatsapp_webhook(
    Body: str = Form(...),           # "table 5 3 idly"
    From: str = Form(...),           # "whatsapp:+919876543210"
    db: Session = Depends(get_db)
):
    """✅ TWILIO WHATSAPP - SAME LOGIC AS /orders/raw"""
    
    print(f"📱 WhatsApp from {From}: '{Body}'")
    
    # 1. Clean with LLM pipeline (EXACT same as /orders/raw)
    cleaning_result = await clean_order(Body)
    
    phone_number = From
    
    if not cleaning_result["success"]:
        # ❌ SAME ERROR LOGIC AS /orders/raw
        reply_msg = f"Please add Table#: {cleaning_result['suggestion']}"
        
        # Send WhatsApp error reply
        client.messages.create(
            from_=TWILIO_WHATSAPP_NUMBER,
            body=reply_msg,
            to=phone_number
        )
        
        return {
            "success": False,
            "error": cleaning_result["error"],
            "whatsapp_reply": reply_msg,
            "status": "error_replied"
        }
    
    # 2. SAME TABLE CHECK + ACTIVE ORDER LOGIC
    clean_order_data = cleaning_result["order"]
    active_order_id = get_active_table_order(clean_order_data["table_num"])
    
    if active_order_id:
        # Update existing order (EXACT SAME)
        order = db.query(Order).filter(Order.id == int(active_order_id)).first()
        if order and order.status not in [OrderStatus.COMPLETED, OrderStatus.CANCELLED]:
            # Add items to existing order (EXACT SAME)
            existing_items = json.loads(order.items)
            new_items = clean_order_data["items"]
            order.items = json.dumps(existing_items + new_items)
            order.total_amount += clean_order_data["total_amount"]
            order.raw_text += f" | {Body}"  # WhatsApp message
            db.commit()
            order_id = order.id
        else:
            order_id = None
            active_order_id = None
    else:
        # Create new order (EXACT SAME)
        active_order_id = None
    
    if not active_order_id:
        # Create new order (EXACT SAME LOGIC)
        db_order = Order(
            table_num=clean_order_data["table_num"],
            items=json.dumps(clean_order_data["items"]),
            total_amount=float(clean_order_data["total_amount"]),
            raw_text=Body,  # WhatsApp message
            status=OrderStatus.NEW
        )
        db.add(db_order)
        db.commit()
        db.refresh(db_order)
        order_id = db_order.id
        set_active_table_order(db_order.table_num, str(order_id))
    
    # 3. SAME BROADCAST LOGIC
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
    
    # 4. WhatsApp SUCCESS reply to waiter
    success_reply = (
        f"✅ *Order #{order_id} Confirmed!*\n"
        f"🪑 Table: {clean_order_data['table_num']}\n"
        f"💰 Total: ₹{clean_order_data['total_amount']}\n"
        f"📦 Items: {len(clean_order_data['items'])}"
    )
    
    client.messages.create(
        from_=TWILIO_WHATSAPP_NUMBER,
        body=success_reply,
        to=phone_number
    )
    
    # 5. SAME RETURN FORMAT AS /orders/raw
    return {
        "success": True, 
        "order_id": order_id, 
        "order": order_data,
        "whatsapp_reply": success_reply,
        "status": "order_processed"
    }
