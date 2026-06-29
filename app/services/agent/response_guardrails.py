from __future__ import annotations

import re

TECHNICAL_PATTERNS = (
    re.compile(r"\b(error_code|traceback|exception|tool_output|invalid_arguments)\b", re.IGNORECASE),
    re.compile(r"^\s*[\[{].*(error|exception).*$", re.IGNORECASE | re.DOTALL),
    re.compile(r"\b(system prompt|developer message|internal instructions?)\b", re.IGNORECASE),
    re.compile(r"\b(api[_ -]?key|token|secret|credenciais?|senha)\b", re.IGNORECASE),
)
OFF_TOPIC_CODE_PATTERNS = (
    re.compile(r"\b(def\s+\w+\s*\(|class\s+\w+|console\.log|SELECT\s+.+\s+FROM)\b", re.IGNORECASE),
    re.compile(r"```"),
)
SAFE_FALLBACK = (
    "Nao consegui confirmar isso agora com seguranca. "
    "Se quiser, posso buscar outro detalhe do imovel ou encaminhar para atendimento humano."
)
OFF_TOPIC_FALLBACK = (
    "Consigo ajudar apenas com informacoes sobre os imoveis, materiais disponiveis "
    "e encaminhamento comercial."
)
MAX_RESPONSE_LENGTH = 600
MARKDOWN_ASTERISK_RE = re.compile(r"(?<!\*)\*{1,2}([^*\n][^*\n]*?)\*{1,2}(?!\*)")


def _strip_markdown_artifacts(text: str) -> str:
    cleaned = MARKDOWN_ASTERISK_RE.sub(lambda match: match.group(1).strip(), text)
    cleaned = cleaned.replace("```", " ")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def sanitize_customer_text(text: str) -> tuple[str, bool]:
    normalized = re.sub(r"\s+", " ", (text or "")).strip()
    if not normalized:
        return SAFE_FALLBACK, True

    sanitized = normalized
    replaced = False
    for pattern in TECHNICAL_PATTERNS:
        if pattern.search(sanitized):
            sanitized = SAFE_FALLBACK
            replaced = True
            break

    if sanitized == normalized:
        for pattern in OFF_TOPIC_CODE_PATTERNS:
            if pattern.search(sanitized):
                sanitized = OFF_TOPIC_FALLBACK
                replaced = True
                break

    cleaned = _strip_markdown_artifacts(sanitized)
    if cleaned != sanitized:
        sanitized = cleaned
        replaced = True

    if len(sanitized) > MAX_RESPONSE_LENGTH:
        sanitized = sanitized[: MAX_RESPONSE_LENGTH - 3].rstrip() + "..."
        replaced = True

    return sanitized, replaced
