from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.orders import router as orders_router
from api.websocket import router as websocket_router
from core.database import engine, Base
import logging
from api.analytics import router as analytics_router
# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="RestaClean API",
    description="Restaurant order cleaning with LLM",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(orders_router, prefix="/api/v1", tags=["orders"])
app.include_router(websocket_router, prefix="/api/v1", tags=["websocket"])
# app.include_router(websocket_router, prefix="/api/v1", tags=["websocket"])
app.include_router(analytics_router, prefix="/api/v1", tags=["analytics"])

# Create tables
Base.metadata.create_all(bind=engine)

@app.get("/")
async def root():
    return {"message": "RestaClean Backend Running ✅"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "1.0.0"}

