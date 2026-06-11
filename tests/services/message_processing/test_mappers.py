from types import SimpleNamespace
from typing import Any

from app.db.models.conversations import SenderType
from app.services.message_processing.mappers import to_agent_messages


def _msg(sender_type: SenderType, content: str | None, attachments: list[Any] | None = None) -> Any:
    return SimpleNamespace(
        sender_type=sender_type,
        content=content,
        attachments=attachments or [],
    )


def _att(mime_type: str | None, url: str = "https://r2.test/a") -> Any:
    return SimpleNamespace(mime_type=mime_type, url=url)


def test_role_mapping_user_and_assistant() -> None:
    out = to_agent_messages(
        [
            _msg(SenderType.USER, "hi"),
            _msg(SenderType.ASSISTANT, "hello"),
        ]
    )

    assert [(m.role, m.text) for m in out] == [("user", "hi"), ("assistant", "hello")]


def test_system_and_human_are_omitted_without_crashing() -> None:
    out = to_agent_messages(
        [
            _msg(SenderType.SYSTEM, "sys"),
            _msg(SenderType.HUMAN, "human agent"),
            _msg(SenderType.USER, "kept"),
        ]
    )

    assert [m.text for m in out] == ["kept"]


def test_attachment_reconstruction_by_mime() -> None:
    out = to_agent_messages(
        [
            _msg(
                SenderType.USER,
                "see attachments",
                [
                    _att("image/png", "https://r2.test/img"),
                    _att("application/pdf", "https://r2.test/doc"),
                    _att("application/zip", "https://r2.test/zip"),
                    _att(None, "https://r2.test/unknown"),
                ],
            )
        ]
    )

    (message,) = out
    kinds = [(a.file_type, a.url) for a in message.attachments]
    assert kinds == [
        ("image", "https://r2.test/img"),
        ("pdf", "https://r2.test/doc"),
    ]


def test_empty_message_without_valid_attachments_is_omitted() -> None:
    out = to_agent_messages(
        [
            _msg(SenderType.USER, "", [_att("application/zip")]),
            _msg(SenderType.USER, None),
        ]
    )

    assert out == []


def test_message_with_only_valid_attachment_is_kept() -> None:
    out = to_agent_messages([_msg(SenderType.USER, "", [_att("image/jpeg")])])

    assert len(out) == 1
    assert out[0].text == ""
    assert out[0].attachments[0].file_type == "image"
