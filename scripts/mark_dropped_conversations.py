import sys
from pathlib import Path

from sqlmodel import Session

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.config import engine
from app.db.repositories.conversations import ConversationMetricRepository


def main() -> None:
    with Session(engine) as db:
        dropped = ConversationMetricRepository(db).mark_inactive_conversations_as_dropped()
        db.commit()
    print(f"dropped_conversations={dropped}")


if __name__ == "__main__":
    main()
