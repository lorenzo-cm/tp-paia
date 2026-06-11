from functools import lru_cache

from app.services.real_estate_rag.service import (
    BuildingRAGService,
    create_building_rag_service,
)


@lru_cache(maxsize=1)
def get_building_rag_service() -> BuildingRAGService:
    return create_building_rag_service()
