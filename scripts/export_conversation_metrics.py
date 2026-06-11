from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from uuid import UUID

from sqlmodel import Session, select

from app.db.config import engine
from app.db.models.conversations import ConversationMetric, FinalOutcome, LeadQuality

METRICS_DIR = Path(__file__).resolve().parents[1] / "metrics"
CONVERSATIONS_DIR = METRICS_DIR / "conversations"
SCHEDULED_COUNT_DESCRIPTION = (
    "Agendamentos proxy via transferencia humana: handoff de leads medium/high. "
    "Refinar quando existir agendamento automatizado real."
)


def _serialize_metric(metric: ConversationMetric) -> dict[str, object]:
    return {
        "conversation_id": str(metric.conversation_id),
        "lead_quality": metric.lead_quality.value if metric.lead_quality else None,
        "qualification_reason": metric.qualification_reason,
        "final_outcome": metric.final_outcome.value if metric.final_outcome else None,
        "used_human_transfer": metric.used_human_transfer,
        "response_time_min_ms": metric.response_time_min_ms,
        "response_time_max_ms": metric.response_time_max_ms,
        "response_time_count": metric.response_time_count,
        "tool_usage": metric.tool_usage or {},
        "created_at": metric.created_at.isoformat(),
        "updated_at": metric.updated_at.isoformat(),
        "closed_at": metric.closed_at.isoformat() if metric.closed_at else None,
    }


def export_conversation(conversation_id: UUID) -> Path:
    with Session(engine) as db:
        metric = db.exec(
            select(ConversationMetric).where(
                ConversationMetric.conversation_id == conversation_id
            )
        ).first()
        if metric is None:
            raise SystemExit(f"conversation_metrics not found for {conversation_id}")
    CONVERSATIONS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = CONVERSATIONS_DIR / f"{conversation_id}.json"
    output_path.write_text(
        json.dumps(_serialize_metric(metric), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return output_path


def export_summary() -> Path:
    with Session(engine) as db:
        metrics = list(db.exec(select(ConversationMetric)).all())
    tool_usage: Counter[str] = Counter()
    for metric in metrics:
        tool_usage.update(
            {
                str(tool_name): int(count)
                for tool_name, count in (metric.tool_usage or {}).items()
            }
        )
    summary = {
        "total_conversations": len(metrics),
        "retained_count": sum(
            1 for metric in metrics if metric.final_outcome == FinalOutcome.RETAINED
        ),
        "handoff_count": sum(
            1 for metric in metrics if metric.final_outcome == FinalOutcome.HANDOFF
        ),
        "dropped_count": sum(
            1 for metric in metrics if metric.final_outcome == FinalOutcome.DROPPED
        ),
        # Nesta versao, handoff humano qualificado e o proxy oficial de agendamento.
        "scheduled_count": sum(
            1
            for metric in metrics
            if metric.final_outcome == FinalOutcome.HANDOFF
            and metric.lead_quality in {LeadQuality.MEDIUM, LeadQuality.HIGH}
        ),
        "tool_usage": dict(sorted(tool_usage.items())),
        "avg_response_count_per_conversation": (
            sum(metric.response_time_count for metric in metrics) / len(metrics)
            if metrics
            else 0
        ),
    }
    METRICS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = METRICS_DIR / "summary.json"
    output_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description=SCHEDULED_COUNT_DESCRIPTION)
    parser.add_argument("--conversation-id", type=UUID)
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()

    wrote_anything = False
    if args.conversation_id is not None:
        export_conversation(args.conversation_id)
        wrote_anything = True
    if args.summary or not wrote_anything:
        export_summary()


if __name__ == "__main__":
    main()
