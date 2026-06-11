from pathlib import Path
from uuid import uuid4

from sqlmodel import Session

from app.db.models.conversations import LeadQuality
from app.db.repositories.conversations import ConversationMetricRepository
from scripts import export_conversation_metrics as export_module
from tests.db.repositories.conversations.factories import make_conversation


def test_export_conversation_and_summary(db_session: Session, tmp_path: Path) -> None:
    conversation_a = make_conversation(db_session, external_id=2001)
    conversation_b = make_conversation(db_session, external_id=2002)
    conversation_c = make_conversation(db_session, external_id=2003)
    repo = ConversationMetricRepository(db_session)

    repo.mark_handoff(
        conversation_a.id,
        lead_quality=LeadQuality.HIGH,
        qualification_reason="Lead pediu visita.",
    )
    repo.increment_tool_usage(conversation_a.id, "transfer_human")
    repo.increment_tool_usage(conversation_a.id, "search_building_information")
    repo.record_response_time(conversation_a.id, 1200)

    repo.update_lead_quality(
        conversation_b.id,
        LeadQuality.LOW,
        "Lead sem sinal claro de avancar.",
    )
    repo.mark_retained(conversation_b.id)
    repo.record_response_time(conversation_b.id, 800)
    repo.mark_handoff(
        conversation_c.id,
        lead_quality=LeadQuality.LOW,
        qualification_reason="Lead transferido sem qualificacao suficiente.",
    )
    db_session.commit()

    export_module.METRICS_DIR = tmp_path / "metrics"
    export_module.CONVERSATIONS_DIR = export_module.METRICS_DIR / "conversations"
    export_module.engine = db_session.get_bind()

    conversation_path = export_module.export_conversation(conversation_a.id)
    summary_path = export_module.export_summary()

    conversation_payload = conversation_path.read_text(encoding="utf-8")
    summary_payload = summary_path.read_text(encoding="utf-8")

    assert str(conversation_a.id) in conversation_payload
    assert '"lead_quality": "high"' in conversation_payload
    assert '"final_outcome": "handoff"' in conversation_payload
    assert '"scheduled_count": 1' in summary_payload
    assert "Agendamentos proxy via transferencia humana" in (
        export_module.SCHEDULED_COUNT_DESCRIPTION
    )
    assert '"retained_count": 1' in summary_payload
    assert '"handoff_count": 2' in summary_payload


def test_export_conversation_raises_when_metric_is_missing(
    db_session: Session, tmp_path: Path
) -> None:
    export_module.METRICS_DIR = tmp_path / "metrics"
    export_module.CONVERSATIONS_DIR = export_module.METRICS_DIR / "conversations"
    export_module.engine = db_session.get_bind()

    try:
        export_module.export_conversation(uuid4())
    except SystemExit as exc:
        assert "conversation_metrics not found" in str(exc)
    else:  # pragma: no cover - defensive branch
        raise AssertionError("expected export_conversation to fail for missing metric")
