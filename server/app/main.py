# FastAPI application entry point

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import settings
from app.core.logging import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    # Pre-load rembg model so first request doesn't download 170MB on the fly
    from app.services.segmentation import get_rembg_session
    import asyncio
    await asyncio.to_thread(get_rembg_session)
    yield


app = FastAPI(
    title="PlankTonne API",
    description="API for measuring resin volume in live edge wood forms",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(router, prefix="/v1")


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}