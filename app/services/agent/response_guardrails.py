from __future__ import annotations

import re

TECHNICAL_PATTERNS = (
    re.compile(r"\b(error_code|traceback|exception|tool_output|invalid_arguments|building_id)\b", re.IGNORECASE),
    re.compile(r"^\s*[\[{].*(error|exception).*$", re.IGNORECASE | re.DOTALL),
)
SAFE_FALLBACK = (
    "Nao consegui confirmar isso agora com seguranca. "
    "Se quiser, posso buscar outro detalhe do imovel ou encaminhar para atendimento humano."
)
MAX_RESPONSE_LENGTH = 600


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

    if len(sanitized) > MAX_RESPONSE_LENGTH:
        sanitized = sanitized[: MAX_RESPONSE_LENGTH - 3].rstrip() + "..."
        replaced = True

    return sanitized, replaced
