"""Shared HTTP helpers (downloads, etc.)."""

import httpx

_client = httpx.AsyncClient(follow_redirects=True)


async def download_bytes(url: str, *, timeout_s: float = 120.0) -> bytes:
    """Fetch binary content from an HTTPS URL."""
    response = await _client.get(url, timeout=timeout_s)
    response.raise_for_status()
    return response.content
