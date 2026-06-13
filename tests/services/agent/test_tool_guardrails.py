from app.services.agent.tool_guardrails import validate_tool_call
from app.services.real_estate_tools import REAL_ESTATE_TOOL_REGISTRY, REAL_ESTATE_TOOLS


def test_tool_call_rejects_extra_fields() -> None:
    result = validate_tool_call(
        tool_name="get_building_info",
        arguments={"building_id": "x", "extra": "nope"},
        tool_registry=REAL_ESTATE_TOOL_REGISTRY,
        tool_definitions=REAL_ESTATE_TOOLS,
    )
    assert result.ok is False
    assert result.error_code == "extra_arguments"


def test_tool_call_rejects_missing_required_fields() -> None:
    result = validate_tool_call(
        tool_name="transfer_human",
        arguments={"summary": "x"},
        tool_registry=REAL_ESTATE_TOOL_REGISTRY,
        tool_definitions=REAL_ESTATE_TOOLS,
    )
    assert result.ok is False
    assert result.error_code == "missing_required_fields"
