from typing import Any

import pytest

from app.services.nsfw.openai_moderation import OpenAINSFWFilter


class FakeModerationCategories:
    def __init__(self, categories: dict[str, bool] | None = None) -> None:
        self._categories = categories or {}

    def model_dump(self) -> dict[str, bool]:
        return dict(self._categories)


class FakeModerationResultItem:
    def __init__(
        self,
        *,
        flagged: bool = False,
        categories: dict[str, bool] | None = None,
    ) -> None:
        self.flagged = flagged
        self.categories = FakeModerationCategories(categories)


class FakeModerationResponse:
    def __init__(self, results: list[FakeModerationResultItem] | None = None) -> None:
        self.results = results if results is not None else [FakeModerationResultItem()]


class _FakeModerations:
    def __init__(self) -> None:
        self.last_call: dict[str, Any] | None = None
        self._next_response: FakeModerationResponse = FakeModerationResponse()
        self._raise: BaseException | None = None

    def set_response(self, response: FakeModerationResponse) -> None:
        self._next_response = response

    def set_error(self, exc: BaseException) -> None:
        self._raise = exc

    async def create(self, **kwargs: Any) -> FakeModerationResponse:
        self.last_call = kwargs
        if self._raise is not None:
            raise self._raise
        return self._next_response


class FakeAsyncOpenAI:
    def __init__(self, **kwargs: Any) -> None:
        self.init_kwargs: dict[str, Any] = kwargs
        self.moderations = _FakeModerations()


@pytest.fixture
def nsfw_filter(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[OpenAINSFWFilter, FakeAsyncOpenAI]:
    fake = FakeAsyncOpenAI()

    def _factory(**kwargs: Any) -> FakeAsyncOpenAI:
        fake.init_kwargs = kwargs
        return fake

    monkeypatch.setattr(
        "app.services.nsfw.openai_moderation.AsyncOpenAI", _factory
    )
    filter_ = OpenAINSFWFilter(api_key="test-key")
    return filter_, fake


def make_openai_api_error(message: str = "boom") -> Exception:
    import httpx
    from openai import APIError

    request = httpx.Request("POST", "https://api.openai.com/v1/moderations")
    return APIError(message, request, body=None)
