"""ContactRepository: idempotent upsert by external id."""

from sqlmodel import Session

from app.db.repositories.conversations import ContactRepository

from .factories import build_contact_create, make_contact, next_external_id


class TestGetOrCreateByExternalId:
    def test_persists_new_contact_when_external_id_unseen(
        self, db_session: Session
    ) -> None:
        external_id = next_external_id()

        created = ContactRepository(db_session).get_or_create_by_external_id(
            external_id, build_contact_create(external_id=external_id, name="Fresh")
        )

        assert created.external_contact_id == external_id

    def test_returns_existing_row_without_overwriting_fields(
        self, db_session: Session
    ) -> None:
        external_id = next_external_id()
        first = make_contact(db_session, external_id=external_id)
        first_name = first.name

        second = ContactRepository(db_session).get_or_create_by_external_id(
            external_id,
            build_contact_create(external_id=external_id, name="Different"),
        )

        assert second.id == first.id
        assert second.name == first_name
