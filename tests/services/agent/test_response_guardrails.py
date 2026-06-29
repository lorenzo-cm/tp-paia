from app.services.agent.response_guardrails import (
    OFF_TOPIC_FALLBACK,
    SAFE_FALLBACK,
    sanitize_customer_text,
)


def test_sanitize_customer_text_replaces_technical_output() -> None:
    text, replaced = sanitize_customer_text(
        '{"error_code":"invalid_arguments","tool_output":{"error":"boom"}}'
    )

    assert text == SAFE_FALLBACK
    assert replaced is True


def test_sanitize_customer_text_replaces_off_topic_code_output() -> None:
    text, replaced = sanitize_customer_text(
        "```python\ndef quicksort(items):\n    return items\n```"
    )

    assert text == OFF_TOPIC_FALLBACK
    assert replaced is True


def test_sanitize_customer_text_strips_markdown_artifacts() -> None:
    text, replaced = sanitize_customer_text("**Apartamento** com *boa* ventilacao.")

    assert text == "Apartamento com boa ventilacao."
    assert replaced is True
