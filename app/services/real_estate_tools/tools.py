from __future__ import annotations

import uuid
from collections.abc import Callable
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import urlparse

from sqlmodel import Session

from app.db.config import engine
from app.db.repositories.buildings import BuildingRepository, normalize_catalog_name
from app.services.real_estate_rag.factory import get_building_rag_service

VALID_LEAD_QUALITIES = {"low", "medium", "high"}


class ToolOutputResponse(dict):
    def __init__(
        self,
        success: bool,
        tool_output: dict[str, Any],
        summary: str = "",
        integration_payload: dict[str, Any] | None = None,
    ) -> None:
        super().__init__()
        self["success"] = success
        self["tool_output"] = tool_output
        self["summary"] = summary
        if integration_payload is not None:
            self["integration_payload"] = integration_payload


REAL_ESTATE_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "name": "get_all_building",
        "description": (
            "List all available buildings by name. Use when the user asks for options, "
            "catalog, alternatives or says they still do not know which profile of property they want."
        ),
        "strict": False,
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "type": "function",
        "name": "get_building_info",
        "description": (
            "Retrieve the confirmed details and media inventory for one building by building_id. "
            "Use before describing characteristics, photos, videos or documents of a building in focus."
        ),
        "strict": False,
        "parameters": {
            "type": "object",
            "properties": {
                "building_id": {
                    "type": "string",
                    "description": "The building ID returned by get_all_building.",
                }
            },
            "required": ["building_id"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "search_building_information",
        "description": (
            "Search the indexed catalog text and return relevant building snippets. "
            "Use to confirm specific facts, compare buildings or answer a question not fully covered by the basic building info."
        ),
        "strict": False,
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The user question or search phrase.",
                },
                "building_id": {
                    "type": "string",
                    "description": "Optional UUID to restrict the search to one building.",
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 10,
                    "description": "Maximum number of snippets to return.",
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "send_photo_file",
        "description": (
            "Send up to two building photos from one requested property part to the user. "
            "Interpret the requested part from file names or environments such as cozinha, banheiro, garagem, jardim or piscina."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "building_id": {"type": "string"},
                "parte_do_imovel": {"type": "string"},
            },
            "required": ["building_id", "parte_do_imovel"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "send_video_file",
        "description": (
            "Send one building video to the user. "
            "Use only after get_building_info confirms an available video for the building in focus."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "building_id": {"type": "string"},
                "video_file_name": {"type": "string"},
            },
            "required": ["building_id", "video_file_name"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "send_building_document",
        "description": (
            "Send one building document to the user. "
            "Use when the user asks for PDF, specifications or more formal material already confirmed in the building inventory."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "building_id": {"type": "string"},
                "document_file_name": {"type": "string"},
            },
            "required": ["building_id", "document_file_name"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "store_lead_house",
        "description": (
            "Store the current building of interest from the user. "
            "Use when the user shows clear interest in a specific property and the conversation starts moving toward qualification."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {"building_id": {"type": "string"}},
            "required": ["building_id"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "transfer_human",
        "description": (
            "Transfer the conversation to a human agent after collecting email. "
            "Use for visit requests, negotiation, proposal, next commercial step or out-of-scope demands that should not stay with the bot."
        ),
        "strict": False,
        "parameters": {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "email": {"type": "string"},
                "lead_quality": {
                    "type": "string",
                    "enum": ["low", "medium", "high"],
                },
                "qualification_reason": {"type": "string"},
            },
            "required": [
                "summary",
                "email",
                "lead_quality",
                "qualification_reason",
            ],
        },
    },
]


def _is_blank(value: Any) -> bool:
    return value is None or not str(value).strip()


def _missing_required_fields_response(
    tool_name: str, missing_fields: list[str]
) -> ToolOutputResponse:
    return ToolOutputResponse(
        False,
        {
            "error": (
                f"Parametros obrigatorios ausentes ou invalidos para {tool_name}: "
                f"{', '.join(missing_fields)}. Reenvie a chamada com esses campos preenchidos."
            ),
            "error_code": "missing_required_fields",
            "missing_fields": missing_fields,
            "tool": tool_name,
        },
    )


def _invalid_building_id_response(
    tool_name: str, building_id: Any
) -> ToolOutputResponse:
    return ToolOutputResponse(
        False,
        {
            "error": (
                f"building_id invalido para {tool_name}: use o ID UUID retornado por "
                "get_all_building."
            ),
            "error_code": "invalid_building_id",
            "building_id": building_id,
            "tool": tool_name,
        },
    )


def _not_found_response(tool_name: str, building_id: Any) -> ToolOutputResponse:
    return ToolOutputResponse(
        False,
        {
            "error": f"building_id nao encontrado para {tool_name}.",
            "error_code": "building_not_found",
            "building_id": building_id,
            "tool": tool_name,
        },
    )


def _parse_building_id(
    tool_name: str, building_id: Any
) -> tuple[uuid.UUID | None, ToolOutputResponse | None]:
    try:
        return uuid.UUID(str(building_id).strip()), None
    except (TypeError, ValueError):
        return None, _invalid_building_id_response(tool_name, building_id)


def _session() -> Session:
    return Session(engine)


def _normalize_path(value: str) -> str:
    parsed = urlparse(value)
    path = parsed.path or value
    return normalize_catalog_name(path.replace("/", " "))


def _basename(value: str) -> str:
    parsed = urlparse(value)
    filename = PurePosixPath(parsed.path).name
    return filename or value


def _pick_urls(urls: list[str], query: str, limit: int | None = None) -> list[str]:
    normalized_query = normalize_catalog_name(query)
    if normalized_query:
        matches = [
            url
            for url in urls
            if normalized_query in _normalize_path(url)
            or normalized_query in normalize_catalog_name(_basename(url))
        ]
    else:
        matches = []
    selected = matches or urls
    if limit is not None:
        return selected[:limit]
    return selected


def get_all_building(**kwargs: Any) -> ToolOutputResponse:
    _ = kwargs
    with _session() as db:
        repo = BuildingRepository(db)
        building_list, building_map = repo.get_all_buildings_and_map_for_tool()
    return ToolOutputResponse(
        True,
        {
            "building_list": building_list,
            "building_map": building_map,
        },
        summary="Lista de empreendimentos carregada.",
    )


def get_building_info(
    building_id: str | None = None, **kwargs: Any
) -> ToolOutputResponse:
    _ = kwargs
    if _is_blank(building_id):
        return _missing_required_fields_response("get_building_info", ["building_id"])
    parsed_building_id, error_response = _parse_building_id(
        "get_building_info", building_id
    )
    if error_response is not None:
        return error_response
    with _session() as db:
        repo = BuildingRepository(db)
        payload = repo.get_building_info_for_tool(parsed_building_id)
    if payload is None:
        return _not_found_response("get_building_info", building_id)
    return ToolOutputResponse(
        True,
        {"type": "get_building_info", **payload},
        summary="Informacoes do empreendimento carregadas.",
    )


def search_building_information(
    query: str | None = None,
    building_id: str | None = None,
    limit: int | None = None,
    **kwargs: Any,
) -> ToolOutputResponse:
    _ = kwargs
    if _is_blank(query):
        return _missing_required_fields_response("search_building_information", ["query"])

    parsed_building_id: uuid.UUID | None = None
    if not _is_blank(building_id):
        parsed_building_id, error_response = _parse_building_id(
            "search_building_information", building_id
        )
        if error_response is not None:
            return error_response

    with _session() as db:
        service = get_building_rag_service()
        resolved_limit = int(limit) if limit is not None else None
        hits = service.build_context(
            str(query).strip(),
            session=db,
            building_id=parsed_building_id,
            limit=resolved_limit,
        )

    matches = [
        {
            "point_id": hit.point_id,
            "building_id": hit.building_id,
            "building_name": hit.building_name,
            "source_url": hit.source_url,
            "chunk_index": hit.chunk_index,
            "text": hit.text,
            "score": hit.score,
        }
        for hit in hits
    ]
    context = service.render_context(hits)
    return ToolOutputResponse(
        True,
        {
            "type": "search_building_information",
            "query": str(query).strip(),
            "building_id": str(parsed_building_id) if parsed_building_id else None,
            "matches": matches,
            "context": context,
        },
        summary="Trechos relevantes do catalogo recuperados.",
    )


def send_photo_file(
    building_id: str | None = None,
    parte_do_imovel: str | None = None,
    **kwargs: Any,
) -> ToolOutputResponse:
    _ = kwargs
    missing_fields: list[str] = []
    if _is_blank(building_id):
        missing_fields.append("building_id")
    if _is_blank(parte_do_imovel):
        missing_fields.append("parte_do_imovel")
    if missing_fields:
        return _missing_required_fields_response("send_photo_file", missing_fields)
    parsed_building_id, error_response = _parse_building_id(
        "send_photo_file", building_id
    )
    if error_response is not None:
        return error_response
    with _session() as db:
        repo = BuildingRepository(db)
        building = repo.get_building_by_tool_id(parsed_building_id)
    if building is None:
        return _not_found_response("send_photo_file", building_id)

    selected_photos = _pick_urls(building.photos_url or [], str(parte_do_imovel), limit=2)
    if not selected_photos:
        return ToolOutputResponse(
            False,
            {
                "type": "send_photo_file",
                "building_id": str(building.id),
                "parte_do_imovel": str(parte_do_imovel).strip(),
                "error": "No photos available for the requested building.",
                "error_code": "media_not_found",
            },
        )

    return ToolOutputResponse(
        True,
        {
            "type": "send_photo_file",
            "building_id": str(building.id),
            "parte_do_imovel": str(parte_do_imovel).strip(),
            "photos_url": selected_photos,
        },
        summary="Fotos selecionadas para o empreendimento.",
    )


def send_video_file(
    building_id: str | None = None,
    video_file_name: str | None = None,
    **kwargs: Any,
) -> ToolOutputResponse:
    _ = kwargs
    missing_fields: list[str] = []
    if _is_blank(building_id):
        missing_fields.append("building_id")
    if _is_blank(video_file_name):
        missing_fields.append("video_file_name")
    if missing_fields:
        return _missing_required_fields_response("send_video_file", missing_fields)
    parsed_building_id, error_response = _parse_building_id(
        "send_video_file", building_id
    )
    if error_response is not None:
        return error_response
    with _session() as db:
        repo = BuildingRepository(db)
        building = repo.get_building_by_tool_id(parsed_building_id)
    if building is None:
        return _not_found_response("send_video_file", building_id)

    requested_name = normalize_catalog_name(str(video_file_name))
    selected_video = next(
        (
            url
            for url in building.videos_url or []
            if requested_name in normalize_catalog_name(_basename(url))
            or requested_name in _normalize_path(url)
        ),
        None,
    )
    if selected_video is None:
        return ToolOutputResponse(
            False,
            {
                "type": "send_video_file",
                "building_id": str(building.id),
                "video_file_name": str(video_file_name).strip(),
                "error": "No video found for the requested building.",
                "error_code": "media_not_found",
            },
        )

    return ToolOutputResponse(
        True,
        {
            "type": "send_video_file",
            "building_id": str(building.id),
            "video_file_name": str(video_file_name).strip(),
            "video_url": selected_video,
        },
        summary="Video selecionado para o empreendimento.",
    )


def send_building_document(
    building_id: str | None = None,
    document_file_name: str | None = None,
    **kwargs: Any,
) -> ToolOutputResponse:
    _ = kwargs
    missing_fields: list[str] = []
    if _is_blank(building_id):
        missing_fields.append("building_id")
    if _is_blank(document_file_name):
        missing_fields.append("document_file_name")
    if missing_fields:
        return _missing_required_fields_response(
            "send_building_document", missing_fields
        )
    parsed_building_id, error_response = _parse_building_id(
        "send_building_document", building_id
    )
    if error_response is not None:
        return error_response
    with _session() as db:
        repo = BuildingRepository(db)
        building = repo.get_building_by_tool_id(parsed_building_id)
    if building is None:
        return _not_found_response("send_building_document", building_id)

    requested_name = normalize_catalog_name(str(document_file_name))
    selected_document = next(
        (
            url
            for url in building.documents_url or []
            if requested_name in normalize_catalog_name(_basename(url))
            or requested_name in _normalize_path(url)
        ),
        None,
    )
    if selected_document is None:
        return ToolOutputResponse(
            False,
            {
                "type": "send_building_document",
                "building_id": str(building.id),
                "document_file_name": str(document_file_name).strip(),
                "error": "No document found for the requested building.",
                "error_code": "media_not_found",
            },
        )

    return ToolOutputResponse(
        True,
        {
            "type": "send_building_document",
            "building_id": str(building.id),
            "document_file_name": str(document_file_name).strip(),
            "document_url": selected_document,
        },
        summary="Documento selecionado para o empreendimento.",
    )


def store_lead_house(building_id: str | None = None, **kwargs: Any) -> ToolOutputResponse:
    _ = kwargs
    if _is_blank(building_id):
        return _missing_required_fields_response("store_lead_house", ["building_id"])
    parsed_building_id, error_response = _parse_building_id(
        "store_lead_house", building_id
    )
    if error_response is not None:
        return error_response
    with _session() as db:
        repo = BuildingRepository(db)
        building = repo.get_building_by_tool_id(parsed_building_id)
    if building is None:
        return _not_found_response("store_lead_house", building_id)

    integration_payload = {
        "lead_interest": {
            "building_id": str(building.id),
            "building_name": building.name,
            "source_url": building.source_url,
        }
    }
    return ToolOutputResponse(
        True,
        {
            "type": "store_lead_house",
            "building_id": str(building.id),
            "building_name": building.name,
            "status": "lead_interest_registered",
        },
        summary="Interesse no empreendimento registrado.",
        integration_payload=integration_payload,
    )


def transfer_human(
    summary: str | None = None,
    email: str | None = None,
    lead_quality: str | None = None,
    qualification_reason: str | None = None,
    **kwargs: Any,
) -> ToolOutputResponse:
    _ = kwargs
    missing_fields: list[str] = []
    if _is_blank(summary):
        missing_fields.append("summary")
    if _is_blank(email):
        missing_fields.append("email")
    if _is_blank(lead_quality):
        missing_fields.append("lead_quality")
    if _is_blank(qualification_reason):
        missing_fields.append("qualification_reason")
    if missing_fields:
        return _missing_required_fields_response("transfer_human", missing_fields)
    normalized_lead_quality = str(lead_quality).strip().lower()
    if normalized_lead_quality not in VALID_LEAD_QUALITIES:
        return ToolOutputResponse(
            False,
            {
                "error": "lead_quality invalido para transfer_human.",
                "error_code": "invalid_lead_quality",
                "lead_quality": lead_quality,
                "allowed_values": sorted(VALID_LEAD_QUALITIES),
                "tool": "transfer_human",
            },
        )
    return ToolOutputResponse(
        True,
        {
            "type": "transfer_human",
            "message": "Transferindo para atendente humano...",
            "summary": str(summary).strip(),
            "email": str(email).strip(),
            "lead_quality": normalized_lead_quality,
            "qualification_reason": str(qualification_reason).strip(),
        },
    )


REAL_ESTATE_TOOL_REGISTRY: dict[str, Callable[..., ToolOutputResponse]] = {
    "get_all_building": get_all_building,
    "get_building_info": get_building_info,
    "search_building_information": search_building_information,
    "send_photo_file": send_photo_file,
    "send_video_file": send_video_file,
    "send_building_document": send_building_document,
    "store_lead_house": store_lead_house,
    "transfer_human": transfer_human,
}
