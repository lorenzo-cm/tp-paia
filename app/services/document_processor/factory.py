from functools import lru_cache

from app.core.config import get_settings
from app.services.document_processor import (
    BaseDocumentProcessor,
    DoclingDocumentProcessor,
)


@lru_cache(maxsize=1)
def get_document_processor() -> BaseDocumentProcessor | None:
    settings = get_settings()
    if settings.DOCUMENT_PROCESSOR_TYPE in (None, "disabled"):
        return None
    on_modal = settings.DOCUMENT_PROCESSOR_TYPE == "docling_modal"
    return DoclingDocumentProcessor(
        on_modal=on_modal,
        modal_app_name=settings.MODAL_APP_NAME if on_modal else None,
        modal_function_name=settings.MODAL_FUNCTION_NAME if on_modal else None,
    )
