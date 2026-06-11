from __future__ import annotations

from types import SimpleNamespace

from app.services.real_estate_rag import tasks


def test_schedule_building_reindex_uses_delay(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    def _delay(payload: dict[str, object]) -> int:
        calls.append(payload)
        return 1

    monkeypatch.setattr(
        tasks,
        "reindex_building_catalog",
        SimpleNamespace(delay=_delay),
    )

    result = tasks.schedule_building_reindex({"building_id": "1"})

    assert result == 1
    assert calls == [{"building_id": "1"}]
