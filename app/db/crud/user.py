from uuid import UUID

from sqlmodel import Session, select

from ..models.user import User, UserCreate


def get_user(db: Session, user_id: UUID) -> User | None:
    statement = select(User).where(User.id == user_id)
    results = db.exec(statement)
    return results.first()


def create_user(db: Session, user_create: UserCreate) -> User:
    db_user = User.model_validate(
        user_create, update={"hashed_password": user_create.password + "_hashed"}
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user
