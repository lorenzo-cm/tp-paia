from uuid import UUID

from sqlmodel import Session, select

from app.db.models.conversations import Contact, ContactCreate, ContactUpdate
from app.db.repositories.base import BaseRepository


class ContactRepository(BaseRepository[Contact, ContactCreate, ContactUpdate, UUID]):
    def __init__(self, db: Session):
        super().__init__(db, Contact)

    def get_by_external_id(self, external_id: int) -> Contact | None:
        statement = select(Contact).where(Contact.external_contact_id == external_id)
        return self.db.exec(statement).first()

    def get_or_create_by_external_id(
        self, external_id: int, defaults: ContactCreate
    ) -> Contact:
        """Idempotent upsert keyed by external_contact_id.

        Caller owns the surrounding transaction; this method only flushes,
        never commits.
        """
        existing = self.get_by_external_id(external_id)
        if existing is not None:
            return existing
        return self.create(defaults)
