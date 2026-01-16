from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from core.database import get_db
from models.order import Order, OrderStatus
from datetime import date, timedelta
from typing import List, Dict, Any
import json

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])

@router.get("/today")
def get_daily_analytics(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Owner Dashboard - Daily Revenue + Metrics"""
    today = date.today()
    
    # Revenue today vs yesterday
    today_revenue = db.query(func.coalesce(func.sum(Order.total_amount), 0)) \
                     .filter(func.date(Order.cleaned_at) == today) \
                     .scalar() or 0.0
    
    yesterday = today - timedelta(days=1)
    yesterday_revenue = db.query(func.coalesce(func.sum(Order.total_amount), 0)) \
                         .filter(func.date(Order.cleaned_at) == yesterday) \
                         .scalar() or 0.0
    
    revenue_change = ((today_revenue - yesterday_revenue) / yesterday_revenue * 100) if yesterday_revenue else 100
    
    # Total orders and avg order value
    total_orders = db.query(func.count(Order.id)) \
                    .filter(func.date(Order.cleaned_at) == today) \
                    .scalar() or 0
    
    avg_order_value = today_revenue / total_orders if total_orders else 0
    
    return {
        "revenue_today": round(today_revenue, 2),
        "revenue_yesterday": round(yesterday_revenue, 2),
        "revenue_change_pct": round(revenue_change, 1),
        "total_orders": total_orders,
        "avg_order_value": round(avg_order_value, 2),
        "date": today.isoformat()
    }

@router.get("/tables/active")
def get_active_tables(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """SIMPLEST VERSION - No complex SQLAlchemy"""
    tables = db.query(Order).filter(
        Order.status.notin_([OrderStatus.SERVED, OrderStatus.CANCELLED])
    ).order_by(Order.table_num).all()
    
    return [
        {
            "table_num": order.table_num,
            "total_amount": round(order.total_amount, 2),
            "status": order.status.value,
            "time_elapsed_minutes": 5  # Frontend calculates live
        }
        for order in tables
    ]


@router.get("/popular-items")
def get_popular_items(db: Session = Depends(get_db)) -> List[Dict]:
    orders = db.query(Order).filter(Order.status != OrderStatus.SERVED).all()
    item_counts = {}
    
    for order in orders:
        items = json.loads(order.items)  # [{"name": "Idly", "qty": 3}]
        for item in items:
            name = item["name"]
            item_counts[name] = item_counts.get(name, 0) + item["qty"]
    
    # Sort by count
    sorted_items = sorted(item_counts.items(), key=lambda x: x[1], reverse=True)
    return [{"item_name": name, "order_count": count} for name, count in sorted_items[:5]]

