from __future__ import annotations

from functools import wraps
from typing import Any

from app.services.real_estate_rag.factory import get_building_rag_service
from app.services.real_estate_rag.service import BuildingRagPayload

try:  # pragma: no cover - exercised only when celery is installed
    from celery import Celery
except ImportError:  # pragma: no cover - local fallback
    Celery = None  # type: ignore[assignment]


def _build_celery_app() -> Any:
    if Celery is None:
        return None
    from app.core.config import get_settings

    settings = get_settings()
    return Celery(
        "template_fastapi",
        broker=settings.CELERY_BROKER_URL,
        backend=settings.CELERY_RESULT_BACKEND,
        include=[__name__],
    )


celery_app = _build_celery_app()


def _as_rag_payload(payload: dict[str, Any]) -> BuildingRagPayload:
    return BuildingRagPayload(
        building_id=str(payload["building_id"]),
        building_name=str(payload["building_name"]),
        source_url=payload.get("source_url"),
        information=str(payload.get("information", "")),
        extraction_version=payload.get("extraction_version"),
    )


def _run_reindex(building_payload: dict[str, Any]) -> int:
    service = get_building_rag_service()
    return service.index_building_payload(_as_rag_payload(building_payload))


if celery_app is not None:  # pragma: no cover - requires celery in environment
    reindex_building_catalog = celery_app.task(
        name="template_fastapi.reindex_building_catalog"
    )(_run_reindex)
else:

    @wraps(_run_reindex)
    def reindex_building_catalog(building_payload: dict[str, Any]) -> int:
        return _run_reindex(building_payload)

    def _delay(building_payload: dict[str, Any]) -> int:
        return _run_reindex(building_payload)

    def _apply_async(
        args: list[Any] | tuple[Any, ...] | None = None,
        kwargs: dict[str, Any] | None = None,
        **_: Any,
    ) -> int:
        payload = kwargs if kwargs is not None else (args[0] if args else {})
        return _run_reindex(dict(payload))

    reindex_building_catalog.delay = _delay  # type: ignore[attr-defined]
    reindex_building_catalog.apply_async = _apply_async  # type: ignore[attr-defined]


def schedule_building_reindex(building_payload: dict[str, Any]) -> Any:
    task = reindex_building_catalog
    delay = getattr(task, "delay", None)
    if callable(delay):
        return delay(building_payload)
    return task(building_payload)
