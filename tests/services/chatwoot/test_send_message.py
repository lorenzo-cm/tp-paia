from unittest.mock import MagicMock, patch

import pytest

from app.services.chatwoot import ChatwootClient


@pytest.fixture
def client() -> ChatwootClient:
    return ChatwootClient(api_url="https://cw.example", api_key="k", account_id=1)


class TestSendMessage:
    @pytest.mark.parametrize("message", ["", "   "])
    def test_rejects_empty_payload(self, client: ChatwootClient, message: str) -> None:
        with patch("app.services.chatwoot.client.httpx.Client") as http_client:
            client.send_message(conversation_id=1, message=message)
            http_client.assert_not_called()

    def test_accepts_attachments_without_text(self, client: ChatwootClient) -> None:
        with patch("app.services.chatwoot.client.httpx.Client") as http_client:
            http_ctx = http_client.return_value.__enter__.return_value
            http_ctx.get.return_value = MagicMock(content=b"x", raise_for_status=lambda: None)
            http_ctx.post.return_value = MagicMock(raise_for_status=lambda: None)

            client.send_message(
                conversation_id=1,
                message="",
                attachments=["https://example.com/file.pdf"],
            )

            assert http_ctx.post.called

    def test_propagates_client_exception(self, client: ChatwootClient) -> None:
        with patch("app.services.chatwoot.client.httpx.Client") as http_client:
            http_ctx = http_client.return_value.__enter__.return_value
            http_ctx.post.side_effect = RuntimeError("network error")

            with pytest.raises(RuntimeError, match="network error"):
                client.send_message(conversation_id=1, message="Hello")

    def test_forwards_payload_to_http(self, client: ChatwootClient) -> None:
        with patch("app.services.chatwoot.client.httpx.Client") as http_client:
            http_ctx = http_client.return_value.__enter__.return_value
            http_ctx.post.return_value = MagicMock(raise_for_status=lambda: None)

            client.send_message(conversation_id=42, message="Hi there")

            http_ctx.post.assert_called_once()
            kwargs = http_ctx.post.call_args.kwargs
            assert "conversations/42/messages" in http_ctx.post.call_args.args[0]
            assert kwargs["data"] == {"content": "Hi there", "message_type": "outgoing"}

    def test_open_conversation_toggles_status_to_open(self, client: ChatwootClient) -> None:
        with patch("app.services.chatwoot.client.httpx.Client") as http_client:
            http_ctx = http_client.return_value.__enter__.return_value
            http_ctx.post.return_value = MagicMock(raise_for_status=lambda: None)

            client.open_conversation(conversation_id=42)

            http_ctx.post.assert_called_once()
            kwargs = http_ctx.post.call_args.kwargs
            assert "conversations/42/toggle_status" in http_ctx.post.call_args.args[0]
            assert kwargs["json"] == {"status": "open"}
