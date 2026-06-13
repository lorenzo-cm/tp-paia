import asyncio
import json
import logging
import time
from dataclasses import dataclass
from typing import Any

from sqlmodel import Session

from app.db.models.conversations import (
    ConversationUpdate,
    InteractionType,
    LeadQuality,
    MessageCreate,
    SenderType,
)
from app.services.agent.base import (
    AgentMessage,
    AgentToolContext,
    BaseAgent,
    ToolResult,
)
from app.services.agent.guardrails import build_model_user_text, inspect_user_text
from app.services.agent.response_guardrails import SAFE_FALLBACK, sanitize_customer_text
from app.services.agent.tool_guardrails import validate_tool_call
from app.services.message_processing.deps import Repos
from app.services.message_processing.mappers import to_agent_messages
from app.services.message_processing.protocols import OutboundSender
from app.services.message_processing.schemas import ConversationContext, Enriched
from app.services.real_estate_tools import REAL_ESTATE_TOOL_REGISTRY, REAL_ESTATE_TOOLS

logger = logging.getLogger(__name__)

DEFAULT_CONVERSATION_META: dict[str, Any] = {
    "sales_stage": "initial_contact",
    "last_building_id": None,
    "handoff_requested": False,
}

VALID_LEAD_QUALITIES = {quality.value for quality in LeadQuality}


@dataclass
class ParsedAgentReply:
    customer_text: str
    lead_quality: LeadQuality | None = None
    qualification_reason: str | None = None
    conversation_concluded: bool = False
    contract_valid: bool = False
    validation_error: str | None = None


async def invoke_agent(
    enriched: Enriched,
    context: ConversationContext,
    repos: Repos,
    db: Session,
    sender: OutboundSender,
    agent: BaseAgent,
    *,
    agent_history_limit: int,
    response_started: float,
) -> None:
    """Build history, run the agent, persist and send the assistant message.

    If there is nothing to answer (no text and no attachments), commits inbound
    rows only and returns.
    """
    if not enriched.combined_text and not enriched.agent_attachments:
        db.commit()
        return
    repos.metric.get_or_create_by_conversation_id(context.conversation_id)
    batch_ids = {row.id for _, row, _ in context.items}
    recent = repos.message.list_recent_with_attachments(
        context.conversation_id, agent_history_limit
    )
    history = to_agent_messages([m for m in recent if m.id not in batch_ids])
    rag_context = _format_rag_context(enriched.rag_context)
    inspection = inspect_user_text(enriched.combined_text)
    if inspection.suspicion:
        _record_guardrail_event(
            context=context,
            repos=repos,
            event="prompt_injection_suspected",
            payload={
                "suspicion": inspection.suspicion,
                "reasons": inspection.reasons,
                "action": inspection.action,
            },
        )
    if inspection.is_strong:
        refusal = (
            "Posso ajudar apenas com informacoes de imoveis e atendimento comercial. "
            "Se voce quiser, encaminho para um atendente humano."
        )
        repos.message.create(
            MessageCreate(
                conversation_id=context.conversation_id,
                sender_participant_id=context.bot_participant_id,
                sender_type=SenderType.ASSISTANT,
                content=refusal,
            )
        )
        db.commit()
        await asyncio.to_thread(sender.send_message, context.conv_ext_id, refusal)
        return
    user_text = build_model_user_text(rag_context=rag_context, user_text=enriched.combined_text)
    user_msg = AgentMessage(
        role="user",
        text=user_text,
        attachments=enriched.agent_attachments,
    )
    tool_events: list[dict[str, Any]] = []
    tool_context = AgentToolContext(
        execute_tool=lambda name, arguments: _execute_tool(
            name, arguments, context, repos, db, sender, tool_events
        )
    )
    response = await agent.run(history, user_msg, tool_context=tool_context)
    parsed = _parse_agent_reply(response.text)
    if not parsed.contract_valid:
        _record_structured_output_failure(
            raw_text=response.text,
            parsed=parsed,
            context=context,
            repos=repos,
        )
        parsed.customer_text = SAFE_FALLBACK
        _record_guardrail_event(
            context=context,
            repos=repos,
            event="agent_output_sanitized",
            payload={"reason": "invalid_structured_output"},
        )
    sanitized_text, sanitized = sanitize_customer_text(parsed.customer_text)
    parsed.customer_text = sanitized_text
    if sanitized:
        _record_guardrail_event(
            context=context,
            repos=repos,
            event="agent_output_sanitized",
            payload={"raw_preview": response.text[:200]},
        )
    repos.message.create(
        MessageCreate(
            conversation_id=context.conversation_id,
            sender_participant_id=context.bot_participant_id,
            sender_type=SenderType.ASSISTANT,
            content=parsed.customer_text,
        )
    )
    db.commit()
    await asyncio.to_thread(sender.send_message, context.conv_ext_id, parsed.customer_text)
    response_time_ms = int((time.monotonic() - response_started) * 1000)
    handoff_succeeded = any(
        event["tool_name"] == "transfer_human" and event["result"].get("success")
        for event in tool_events
    )
    if parsed.contract_valid and not handoff_succeeded and (
        parsed.lead_quality is not None or parsed.qualification_reason is not None
    ):
        repos.metric.update_lead_quality(
            context.conversation_id,
            parsed.lead_quality,
            parsed.qualification_reason,
        )
    if parsed.contract_valid and parsed.conversation_concluded and not handoff_succeeded:
        repos.metric.mark_retained(context.conversation_id)
    repos.metric.record_response_time(context.conversation_id, response_time_ms)
    db.commit()


async def _execute_tool(
    tool_name: str,
    arguments: dict[str, Any],
    context: ConversationContext,
    repos: Repos,
    db: Session,
    sender: OutboundSender,
    tool_events: list[dict[str, Any]],
) -> ToolResult:
    started = time.monotonic()
    call_meta = {
        "event": "tool_called",
        "tool_name": tool_name,
        "arguments": arguments,
    }
    repos.message.create(
        MessageCreate(
            conversation_id=context.conversation_id,
            sender_participant_id=context.bot_participant_id,
            sender_type=SenderType.SYSTEM,
            interaction_type=InteractionType.TOOL_CALL,
            content=json.dumps(
                {"name": tool_name, "arguments": arguments},
                ensure_ascii=False,
                default=str,
            ),
            meta=call_meta,
        )
    )
    db.flush()

    tool = REAL_ESTATE_TOOL_REGISTRY.get(tool_name)
    if "_invalid_json" in arguments:
        result = {
            "success": False,
            "tool_output": {
                "error": "Nao foi possivel interpretar os parametros da acao.",
                "error_code": "invalid_arguments",
                "tool": tool_name,
            },
        }
    else:
        validation = validate_tool_call(
            tool_name=tool_name,
            arguments=arguments,
            tool_registry=REAL_ESTATE_TOOL_REGISTRY,
            tool_definitions=REAL_ESTATE_TOOLS,
        )
        if not validation.ok:
            _record_guardrail_event(
                context=context,
                repos=repos,
                event="tool_call_rejected",
                payload={
                    "tool_name": tool_name,
                    "error_code": validation.error_code,
                },
            )
            result = {
                "success": False,
                "tool_output": {
                    "error": "Nao foi possivel executar essa acao automaticamente.",
                    "error_code": validation.error_code,
                    "tool": tool_name,
                },
            }
        elif tool is None:
            result = {
                "success": False,
                "tool_output": {
                    "error": "Nao foi possivel executar essa acao automaticamente.",
                    "error_code": "unknown_tool",
                    "tool": tool_name,
                },
            }
        else:
            try:
                result = dict(await asyncio.to_thread(tool, **arguments))
            except Exception:  # pragma: no cover - defensive boundary
                logger.warning(
                    "tool execution failed",
                    extra={"tool_name": tool_name},
                    exc_info=True,
                )
                result = {
                    "success": False,
                    "tool_output": {
                        "error": "Nao foi possivel concluir essa acao automaticamente.",
                        "error_code": "tool_execution_failed",
                        "tool": tool_name,
                    },
                }

    media_urls = _extract_media_urls(result)
    media_events = await _send_tool_media(sender, context.conv_ext_id, media_urls)
    if media_events:
        result = {**result, "media_events": media_events}

    repos.metric.increment_tool_usage(context.conversation_id, tool_name)
    if tool_name == "transfer_human" and result.get("success"):
        lead_quality = _parse_lead_quality(arguments.get("lead_quality"))
        qualification_reason = str(arguments.get("qualification_reason") or "").strip()
        if lead_quality is not None and qualification_reason:
            repos.metric.mark_handoff(
                context.conversation_id,
                lead_quality=lead_quality,
                qualification_reason=qualification_reason,
            )

    _update_conversation_meta(tool_name, arguments, result, context, repos)
    duration_ms = int((time.monotonic() - started) * 1000)
    event_name = "tool_success" if result.get("success") else "tool_failed"
    repos.message.create(
        MessageCreate(
            conversation_id=context.conversation_id,
            sender_participant_id=context.bot_participant_id,
            sender_type=SenderType.SYSTEM,
            interaction_type=InteractionType.TOOL_RESPONSE,
            content=json.dumps(result, ensure_ascii=False, default=str),
            meta={
                "event": event_name,
                "tool_name": tool_name,
                "success": bool(result.get("success")),
                "arguments": arguments,
                "duration_ms": duration_ms,
                "media_urls": media_urls,
                "media_events": media_events,
            },
        )
    )
    db.flush()
    tool_events.append(
        {
            "tool_name": tool_name,
            "arguments": arguments,
            "result": result,
        }
    )
    return ToolResult(output=result, media_urls=media_urls)


def _extract_media_urls(result: dict[str, Any]) -> list[str]:
    output = result.get("tool_output") or {}
    urls: list[str] = []
    for key in ("photos_url", "video_url", "document_url"):
        value = output.get(key)
        if isinstance(value, list):
            urls.extend(str(item) for item in value if item)
        elif value:
            urls.append(str(value))
    return urls


async def _send_tool_media(
    sender: OutboundSender, conversation_id: int, media_urls: list[str]
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for url in media_urls:
        try:
            await asyncio.to_thread(
                sender.send_message, conversation_id, "", attachments=[url]
            )
            events.append({"event": "media_sent", "url": url, "success": True})
        except Exception as exc:
            events.append(
                {
                    "event": "media_send_failed",
                    "url": url,
                    "success": False,
                    "error": str(exc),
                    "fallback_text": f"Nao consegui enviar o anexo automaticamente: {url}",
                }
            )
    return events


def _update_conversation_meta(
    tool_name: str,
    arguments: dict[str, Any],
    result: dict[str, Any],
    context: ConversationContext,
    repos: Repos,
) -> None:
    conversation = repos.conversation.get(context.conversation_id)
    if conversation is None:
        return
    meta = {**DEFAULT_CONVERSATION_META, **(conversation.meta or {})}
    output = result.get("tool_output") or {}
    if tool_name in {"get_all_building", "search_building_information"}:
        meta["sales_stage"] = "information"
    if tool_name in {"get_building_info", "store_lead_house"} and result.get("success"):
        building_id = output.get("building_id") or arguments.get("building_id")
        if building_id:
            meta["last_building_id"] = str(building_id)
        meta["sales_stage"] = "qualification"
    if tool_name == "transfer_human" and result.get("success"):
        meta["handoff_requested"] = True
        meta["sales_stage"] = "human_transfer"
        meta["last_event"] = "human_transfer_requested"
    repos.conversation.update(ConversationUpdate(id=context.conversation_id, meta=meta))


def _format_rag_context(rag_context: list[object]) -> str:
    if not rag_context:
        return ""
    lines = ["Contexto recuperado do catalogo imobiliario:"]
    for index, hit in enumerate(rag_context, start=1):
        building_name = getattr(hit, "building_name", "")
        chunk_index = getattr(hit, "chunk_index", 0)
        score = getattr(hit, "score", 0.0)
        source_url = getattr(hit, "source_url", None)
        text = getattr(hit, "text", "")
        suffix = f" | fonte: {source_url}" if source_url else ""
        lines.append(
            f"{index}. {building_name} (chunk {chunk_index}, score {float(score):.3f}){suffix}"
        )
        lines.append(f"   Trecho: {text}")
    return "\n".join(lines)


def _parse_agent_reply(raw_text: str) -> ParsedAgentReply:
    stripped = raw_text.strip()
    if not stripped:
        return ParsedAgentReply(
            customer_text="",
            validation_error="empty_response",
        )
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        return ParsedAgentReply(
            customer_text=raw_text,
            validation_error="invalid_json",
        )
    if not isinstance(payload, dict):
        return ParsedAgentReply(
            customer_text=raw_text,
            validation_error="json_root_must_be_object",
        )
    response_value = payload.get("response")
    response_text = response_value.strip() if isinstance(response_value, str) else ""
    customer_text = response_text or raw_text
    required_keys = {
        "response",
        "lead_quality",
        "qualification_reason",
        "conversation_concluded",
    }
    if set(payload) != required_keys:
        return ParsedAgentReply(
            customer_text=customer_text,
            validation_error="invalid_keys",
        )
    lead_quality = _parse_lead_quality(payload.get("lead_quality"))
    qualification_reason = _parse_qualification_reason(
        payload.get("qualification_reason")
    )
    conversation_concluded = payload.get("conversation_concluded")
    if not response_text:
        validation_error = "invalid_response"
    elif lead_quality is None:
        validation_error = "invalid_lead_quality"
    elif qualification_reason is None:
        validation_error = "invalid_qualification_reason"
    elif not isinstance(conversation_concluded, bool):
        validation_error = "invalid_conversation_concluded"
    else:
        validation_error = None
    if validation_error is not None:
        return ParsedAgentReply(
            customer_text=customer_text,
            validation_error=validation_error,
        )
    return ParsedAgentReply(
        customer_text=response_text,
        lead_quality=lead_quality,
        qualification_reason=qualification_reason,
        conversation_concluded=conversation_concluded,
        contract_valid=True,
    )


def _record_structured_output_failure(
    *,
    raw_text: str,
    parsed: ParsedAgentReply,
    context: ConversationContext,
    repos: Repos,
) -> None:
    logger.warning(
        "agent structured output validation failed",
        extra={
            "conversation_id": str(context.conversation_id),
            "validation_error": parsed.validation_error,
        },
    )
    repos.message.create(
        MessageCreate(
            conversation_id=context.conversation_id,
            sender_participant_id=context.bot_participant_id,
            sender_type=SenderType.SYSTEM,
            content=json.dumps(
                {
                    "error": parsed.validation_error,
                    "raw_response": raw_text,
                },
                ensure_ascii=False,
            ),
            meta={
                "event": "agent_structured_output_invalid",
                "validation_error": parsed.validation_error,
            },
        )
    )
    conversation = repos.conversation.get(context.conversation_id)
    current_meta = conversation.meta if conversation and conversation.meta else {}
    repos.conversation.update(
        ConversationUpdate(
            id=context.conversation_id,
            meta={
                **DEFAULT_CONVERSATION_META,
                **current_meta,
                "last_system_error": "agent_structured_output_invalid",
            },
        )
    )


def _record_guardrail_event(
    *,
    context: ConversationContext,
    repos: Repos,
    event: str,
    payload: dict[str, Any],
) -> None:
    logger.warning(
        "guardrail event",
        extra={
            "conversation_id": str(context.conversation_id),
            "event": event,
            **payload,
        },
    )
    repos.message.create(
        MessageCreate(
            conversation_id=context.conversation_id,
            sender_participant_id=context.bot_participant_id,
            sender_type=SenderType.SYSTEM,
            content=json.dumps(payload, ensure_ascii=False, default=str),
            meta={"event": event, **payload},
        )
    )


def _parse_lead_quality(value: Any) -> LeadQuality | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    if normalized not in VALID_LEAD_QUALITIES:
        return None
    return LeadQuality(normalized)


def _parse_qualification_reason(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
