from app.services.message_processing.deps import Repos
from app.services.message_processing.schemas import Enriched
from app.services.real_estate_rag.factory import get_building_rag_service
from app.core.config import get_settings


def rag_index(enriched: Enriched, repos: Repos) -> Enriched:
    """Fetch catalog snippets relevant to the current user message."""
    if not enriched.combined_text.strip():
        enriched.rag_context = []
        return enriched

    service = get_building_rag_service()
    enriched.rag_context = service.build_context(
        enriched.combined_text,
        session=repos.building.db,
        limit=get_settings().RAG_MAX_CONTEXT_CHUNKS,
    )
    return enriched
