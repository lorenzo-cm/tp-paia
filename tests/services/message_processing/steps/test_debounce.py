"""Isolated tests for ``debounce``.

``test_pipeline.py`` covers end-to-end behavior; these pin the step contract.
"""

from typing import Any

import pytest

from app.services.message_debouncer.service import DebounceInfo
from app.services.message_processing.schemas import (
    InboundMessage,
    serialize_inbound,
)
from app.services.message_processing.steps.debounce import debounce


def _msg(ext_id: str = "1", conv_id: str = "9001") -> InboundMessage:
    return InboundMessage(
        external_message_id=ext_id,
        external_conversation_id=conv_id,
        inbox_ref="42",
        contact_external_id="7",
        contact_name="Alice",
        contact_phone="+5511999",
        text="hi",
    )


class _FakeDebouncer:
    def __init__(self, info: DebounceInfo | None) -> None:
        self._info = info
        self.calls: list[tuple[str, str]] = []

    async def debounce(self, conv_id: str, payload: str) -> DebounceInfo | None:
        self.calls.append((conv_id, payload))
        return self._info


@pytest.mark.asyncio
async def test_debounce_non_final_caller_returns_none() -> None:
    d: Any = _FakeDebouncer(info=None)
    msg = _msg()
    assert await debounce(d, msg) is None
    # called with conv id + serialized msg
    assert d.calls[0][0] == "9001"
    assert "external_message_id" in d.calls[0][1]


@pytest.mark.asyncio
async def test_debounce_final_caller_returns_full_batch() -> None:
    m1, m2 = _msg("1"), _msg("2")
    info = DebounceInfo(
        payloads=[serialize_inbound(m1), serialize_inbound(m2)], attempts=1
    )
    d: Any = _FakeDebouncer(info=info)
    batch = await debounce(d, m1)
    assert batch is not None
    assert [m.external_message_id for m in batch] == ["1", "2"]
