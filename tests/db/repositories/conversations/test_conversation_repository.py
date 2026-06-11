"""ConversationRepository: idempotent upsert by external id."""

from sqlmodel import Session

from app.db.repositories.conversations import ConversationRepository

from .factories import build_conversation_create, next_external_id


class TestGetOrCreateByExternalId:
    def test_persists_new_conversation_when_external_id_unseen(
        self, db_session: Session
    ) -> None:
        external_id = next_external_id()
        repo = ConversationRepository(db_session)

        created = repo.get_or_create_by_external_id(
            external_id, build_conversation_create(external_id=external_id)
        )

        assert created.external_conversation_id == external_id

    def test_returns_existing_row_without_overwriting_fields(
        self, db_session: Session
    ) -> None:
        external_id = next_external_id()
        repo = ConversationRepository(db_session)
        first = repo.get_or_create_by_external_id(
            external_id,
            build_conversation_create(external_id=external_id, inbox_id=1),
        )

        second = repo.get_or_create_by_external_id(
            external_id,
            build_conversation_create(external_id=external_id, inbox_id=999),
        )

        assert second.id == first.id
        assert second.inbox_id == 1, "second call must not overwrite existing fields"
