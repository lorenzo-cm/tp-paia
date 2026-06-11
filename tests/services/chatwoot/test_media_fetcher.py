import pytest

from app.services.chatwoot import media_fetcher as media_fetcher_module
from app.services.chatwoot.media_fetcher import ChatwootMediaFetcher
from app.services.message_processing.schemas import InboundAttachment


async def test_fetch_downloads_from_url(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, str] = {}

    async def fake_download(url: str) -> bytes:
        seen["url"] = url
        return b"binary-bytes"

    monkeypatch.setattr(media_fetcher_module, "download_bytes", fake_download)

    att = InboundAttachment(
        file_type="image",
        media_ref="https://cw.example/files/photo.png",
        url="https://cw.example/files/photo.png",
    )
    result = await ChatwootMediaFetcher().fetch(att)

    assert result == b"binary-bytes"
    assert seen["url"] == "https://cw.example/files/photo.png"


async def test_fetch_raises_when_url_none() -> None:
    att = InboundAttachment(file_type="image", media_ref="ref", url=None)

    with pytest.raises(ValueError):
        await ChatwootMediaFetcher().fetch(att)
