from .main import router as v1_router
from .user import router as user_router

v1_router.include_router(user_router)

__all__ = ["v1_router"]
