from abc import ABC, abstractmethod

from app.core.http import download_bytes


class DocumentProcessingError(Exception):
    """Raised when document extraction fails or configuration is invalid."""


class BaseDocumentProcessor(ABC):
    async def process(
        self,
        file_input: bytes | str,
    ) -> str:
        if isinstance(file_input, str):
            file_bytes = await download_bytes(file_input)
        else:
            file_bytes = file_input
        return await self._do_process(file_bytes)

    @abstractmethod
    async def _do_process(
        self,
        file_bytes: bytes,
    ) -> str: ...
