from typing import Any

import pytest

from app.core.config import get_settings
from app.services.nsfw.base import ModerationResult
from app.services.nsfw.exceptions import NSFWError
from app.services.nsfw.openai_moderation import OpenAINSFWFilter
from tests.services.nsfw.conftest import (
    FakeAsyncOpenAI,
    FakeModerationResponse,
    FakeModerationResultItem,
    make_openai_api_error,
)

settings = get_settings()


class TestConstruction:

    def test_raises_when_api_key_is_empty(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "app.services.nsfw.openai_moderation.AsyncOpenAI",
            lambda **kw: FakeAsyncOpenAI(**kw),
        )
        with pytest.raises(NSFWError):
            OpenAINSFWFilter(api_key="")

    def test_accepts_constructor_api_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: dict[str, Any] = {}

        def _factory(**kwargs: Any) -> FakeAsyncOpenAI:
            captured.update(kwargs)
            return FakeAsyncOpenAI(**kwargs)

        monkeypatch.setattr(
            "app.services.nsfw.openai_moderation.AsyncOpenAI", _factory
        )
        OpenAINSFWFilter(api_key="from-arg")
        assert captured["api_key"] == "from-arg"


class TestModeration:

    async def test_is_safe_text_returns_moderation_result(
        self, nsfw_filter: tuple[OpenAINSFWFilter, FakeAsyncOpenAI]
    ) -> None:
        filter_, fake = nsfw_filter
        fake.moderations.set_response(
            FakeModerationResponse(
                results=[FakeModerationResultItem(flagged=False, categories={})]
            )
        )
        result = await filter_.is_safe_text("hello")
        assert isinstance(result, ModerationResult)
        assert result.is_safe is True
        assert result.flagged_categories == []

    async def test_is_safe_image_returns_moderation_result(
        self, nsfw_filter: tuple[OpenAINSFWFilter, FakeAsyncOpenAI]
    ) -> None:
        filter_, fake = nsfw_filter
        fake.moderations.set_response(
            FakeModerationResponse(
                results=[FakeModerationResultItem(flagged=False, categories={})]
            )
        )
        result = await filter_.is_safe_image("https://example.com/x.png")
        assert isinstance(result, ModerationResult)
        assert result.is_safe is True
        assert result.flagged_categories == []

    async def test_flagged_response_marks_unsafe_and_lists_categories(
        self, nsfw_filter: tuple[OpenAINSFWFilter, FakeAsyncOpenAI]
    ) -> None:
        filter_, fake = nsfw_filter
        fake.moderations.set_response(
            FakeModerationResponse(
                results=[
                    FakeModerationResultItem(
                        flagged=True,
                        categories={
                            "sexual": True,
                            "violence": True,
                            "hate": False,
                        },
                    )
                ]
            )
        )
        result = await filter_.is_safe_text("nasty")
        assert result.is_safe is False
        assert "sexual" in result.flagged_categories
        assert "violence" in result.flagged_categories
        assert "hate" not in result.flagged_categories

    async def test_clean_response_returns_safe_with_empty_categories(
        self, nsfw_filter: tuple[OpenAINSFWFilter, FakeAsyncOpenAI]
    ) -> None:
        filter_, fake = nsfw_filter
        fake.moderations.set_response(
            FakeModerationResponse(
                results=[
                    FakeModerationResultItem(
                        flagged=False,
                        categories={"sexual": False, "violence": False},
                    )
                ]
            )
        )
        result = await filter_.is_safe_text("polite")
        assert result.is_safe is True
        assert result.flagged_categories == []


class TestShape:

    async def test_text_input_shape_is_exact(
        self, nsfw_filter: tuple[OpenAINSFWFilter, FakeAsyncOpenAI]
    ) -> None:
        filter_, fake = nsfw_filter
        await filter_.is_safe_text("hello world")
        assert fake.moderations.last_call == {
            "model": "omni-moderation-latest",
            "input": "hello world",
        }

    async def test_image_input_shape_is_exact(
        self, nsfw_filter: tuple[OpenAINSFWFilter, FakeAsyncOpenAI]
    ) -> None:
        filter_, fake = nsfw_filter
        await filter_.is_safe_image("https://example.com/img.png")
        assert fake.moderations.last_call == {
            "model": "omni-moderation-latest",
            "input": [
                {
                    "type": "image_url",
                    "image_url": {"url": "https://example.com/img.png"},
                }
            ],
        }


class TestErrorHandling:

    async def test_apierror_is_wrapped_in_nsfw_error_with_cause(
        self, nsfw_filter: tuple[OpenAINSFWFilter, FakeAsyncOpenAI]
    ) -> None:
        filter_, fake = nsfw_filter
        original = make_openai_api_error("boom")
        fake.moderations.set_error(original)
        with pytest.raises(NSFWError) as exc_info:
            await filter_.is_safe_text("hi")
        assert exc_info.value.__cause__ is original
