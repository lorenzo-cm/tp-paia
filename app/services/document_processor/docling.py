import asyncio
from io import BytesIO
from typing import cast

from docling.datamodel.base_models import DocumentStream
from docling.document_converter import DocumentConverter

from app.services.document_processor.base import (
    BaseDocumentProcessor,
)

converter = DocumentConverter()


def docling_process_local(file_bytes: bytes) -> str:
    stream = DocumentStream(name="document.pdf", stream=BytesIO(file_bytes))
    result = converter.convert(stream)
    return cast(str, result.document.export_to_markdown())


async def docling_process_modal(
    file_bytes: bytes, modal_app_name: str, modal_function_name: str
) -> str:
    from modal.functions import Function

    remote_fn = Function.from_name(modal_app_name, modal_function_name)
    return cast(str, await remote_fn.remote.aio(file_bytes))


class DoclingDocumentProcessor(BaseDocumentProcessor):
    """Runs Docling `DocumentConverter` in a worker thread (sync docling API)."""

    def __init__(
        self,
        *,
        on_modal: bool = False,
        modal_app_name: str | None = None,
        modal_function_name: str | None = None,
    ) -> None:
        self.on_modal = on_modal
        self._modal_app_name = modal_app_name
        self._modal_function_name = modal_function_name

    async def _do_process(
        self,
        file_bytes: bytes,
    ) -> str:
        if self.on_modal:
            if not self._modal_app_name or not self._modal_function_name:
                raise ValueError(
                    "on_modal=True requires modal_app_name and modal_function_name"
                )
            return await docling_process_modal(
                file_bytes, self._modal_app_name, self._modal_function_name
            )
        return await asyncio.to_thread(docling_process_local, file_bytes)
