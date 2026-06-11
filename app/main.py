from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import main_router
from app.core.auth import auth_router
from app.core.config import get_settings
from app.core.logger import setup_logging
from app.exceptions.handlers import init_exception_handlers

settings = get_settings()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    redoc_url=f"{settings.API_PREFIX}/redoc",
    openapi_url=f"{settings.API_PREFIX}/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

setup_logging()
init_exception_handlers(app)

app.include_router(auth_router, prefix=f"{settings.API_PREFIX}")
app.include_router(main_router, prefix=f"{settings.API_PREFIX}")
