from types import SimpleNamespace
from typing import Any

from app.db.models.conversations import InteractionType, SenderType
from app.services.message_processing.mappers import to_agent_messages


def _msg(
    sender_type: SenderType,
    content: str | None,
    attachments: list[Any] | None = None,
    *,
    interaction_type: InteractionType = InteractionType.CHAT,
    meta: dict[str, Any] | None = None,
) -> Any:
    return SimpleNamespace(
        sender_type=sender_type,
        content=content,
        attachments=attachments or [],
        interaction_type=interaction_type,
        meta=meta,
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


def test_successful_media_send_becomes_assistant_note() -> None:
    out = to_agent_messages(
        [
            _msg(SenderType.USER, "manda o video"),
            _msg(
                SenderType.SYSTEM,
                '{"success": true}',
                interaction_type=InteractionType.TOOL_RESPONSE,
                meta={
                    "event": "tool_success",
                    "tool_name": "send_video_file",
                    "media_urls": ["https://cdn.example.com/aurora/tour.mp4"],
                },
            ),
        ]
    )

    assert [(m.role, m.text) for m in out] == [
        ("user", "manda o video"),
        ("assistant", "[midia ja enviada ao cliente: tour.mp4]"),
    ]


def test_failed_or_non_media_tool_responses_are_omitted() -> None:
    out = to_agent_messages(
        [
            _msg(
                SenderType.SYSTEM,
                "{}",
                interaction_type=InteractionType.TOOL_RESPONSE,
                meta={
                    "event": "tool_failed",
                    "tool_name": "send_video_file",
                    "media_urls": [],
                },
            ),
            _msg(
                SenderType.SYSTEM,
                "{}",
                interaction_type=InteractionType.TOOL_RESPONSE,
                meta={"event": "tool_success", "tool_name": "get_all_building"},
            ),
            _msg(SenderType.USER, "kept"),
        ]
    )

    assert [m.text for m in out] == ["kept"]
