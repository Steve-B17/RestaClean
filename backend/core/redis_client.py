import redis
from typing import Optional
from config import settings

redis_client = redis.Redis.from_url(settings.redis_url, decode_responses=True)

def test_connection() -> bool:
    try:
        return redis_client.ping()
    except:
        return False

def push_order_to_queue(order_data: dict) -> bool:
    """Add order to processing queue"""
    return redis_client.lpush("order_queue", str(order_data))

def pop_order_from_queue() -> Optional[str]:
    """Get next order from queue"""
    result = redis_client.brpop("order_queue", timeout=5)
    return result[1] if result else None

def get_active_table_order(table_num: int) -> Optional[str]:
    """Get current order for table"""
    return redis_client.get(f"active_table:{table_num}")

def set_active_table_order(table_num: int, order_id: str, ttl: int = 3600):
    """Set current order for table (1 hour TTL)"""
    redis_client.setex(f"active_table:{table_num}", ttl, order_id)
