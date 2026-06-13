from __future__ import annotations

from dataclasses import dataclass
from typing import Any

MAX_STRING_ARG_LENGTH = 500


@dataclass(slots=True)
class ToolGuardrailResult:
    ok: bool
    error_code: str | None = None
    message: str | None = None


def validate_tool_call(
    *,
    tool_name: str,
    arguments: Any,
    tool_registry: dict[str, Any],
    tool_definitions: list[dict[str, Any]],
) -> ToolGuardrailResult:
    if tool_name not in tool_registry:
        return ToolGuardrailResult(False, "unknown_tool", "Tool solicitada nao existe.")
    if not isinstance(arguments, dict):
        return ToolGuardrailResult(False, "invalid_arguments", "Argumentos da tool devem ser um objeto JSON.")

    tool_def = next((tool for tool in tool_definitions if tool["name"] == tool_name), None)
    params = (tool_def or {}).get("parameters", {})
    required = set(params.get("required", []))
    properties = set((params.get("properties") or {}).keys())

    extra_fields = sorted(set(arguments) - properties)
    if extra_fields:
        return ToolGuardrailResult(False, "extra_arguments", "A chamada da tool contem campos nao permitidos.")

    missing = sorted(
        field for field in required if field not in arguments or _is_blank(arguments.get(field))
    )
    if missing:
        return ToolGuardrailResult(False, "missing_required_fields", "A chamada da tool esta sem campos obrigatorios.")

    for key, value in arguments.items():
        if isinstance(value, str) and len(value) > MAX_STRING_ARG_LENGTH:
            return ToolGuardrailResult(False, "argument_too_long", f"O campo {key} excede o limite permitido.")

    return ToolGuardrailResult(True)


def _is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())
