import httpx
from typing import Optional
from config import settings

async def send_whatsapp_reply(phone_number: str, message: str) -> bool:
    """Send error reply to waiter"""
    if not settings.whatsapp_token:
        print(f"[WhatsApp Mock] To {phone_number}: {message}")
        return True
    
    url = "https://graph.facebook.com/v18.0/YOUR_PHONE_ID/messages"
    headers = {
        "Authorization": f"Bearer {settings.whatsapp_token}",
        "Content-Type": "application/json"
    }
    data = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "text",
        "text": {"body": message}
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=data, headers=headers)
        return response.status_code == 200

async def parse_whatsapp_webhook(request: dict) -> Optional[str]:
    """Extract text from WhatsApp webhook"""
    try:
        entry = request["entry"][0]["changes"][0]["value"]
        if entry["messages"]:
            return entry["messages"][0]["text"]["body"]
        return None
    except (KeyError, IndexError):
        return None
