from fastapi import APIRouter

from app.api.v1.main import router as v1_router

main_router = APIRouter()


@main_router.get("/health")
def health() -> dict[str, str]:
    return {"status": "API Working!"}


main_router.include_router(v1_router, prefix="/v1")
