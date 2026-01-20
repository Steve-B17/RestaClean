from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    database_url: str
    redis_url: str = "redis://localhost:6379/0"
    groq_api_key: str
    whatsapp_token: Optional[str] = None
    secret_key: str = "change-in-production"
    debug: bool = True
    twilio_account_sid: str
    twilio_auth_token: str
    twilio_whatsapp_number: str
    
    class Config:
        env_file = ".env"

settings = Settings()
