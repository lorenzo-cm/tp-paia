from sqlmodel import Session

from app.db.config import engine
from app.db.repositories.conversations import ConversationMetricRepository


def main() -> None:
    with Session(engine) as db:
        dropped = ConversationMetricRepository(db).mark_inactive_conversations_as_dropped()
        db.commit()
    print(f"dropped_conversations={dropped}")


if __name__ == "__main__":
    main()
