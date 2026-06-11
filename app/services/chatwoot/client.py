import httpx
import magic

AttachmentFile = tuple[str, tuple[str, bytes, str]]


class ChatwootClient:
    def __init__(
        self,
        *,
        api_url: str,
        api_key: str,
        account_id: int,
    ) -> None:
        self._api_url = api_url
        self._api_key = api_key
        self._account_id = account_id

    def send_message(
        self,
        conversation_id: int,
        message: str = "",
        attachments: list[str] | None = None,
    ) -> None:
        message = message.strip()
        attachments = attachments or []
        if not message and not attachments:
            return

        with httpx.Client() as client:
            for msg_content, msg_attachments in self._split_sends(message, attachments):
                response = client.post(
                    self._build_message_url(conversation_id),
                    headers=self._build_headers(),
                    data={"content": msg_content, "message_type": "outgoing"},
                    timeout=30.0,
                    files=self._process_attachments(client, msg_attachments),
                )
                response.raise_for_status()

    def _build_headers(self) -> dict[str, str]:
        return {"api_access_token": self._api_key}

    def _build_message_url(self, conversation_id: int) -> str:
        return (
            f"{self._api_url}/api/v1/accounts/"
            f"{self._account_id}/conversations/{conversation_id}/messages"
        )

    def _split_sends(
        self, content: str, attachments: list[str]
    ) -> list[tuple[str, list[str]]]:
        """WhatsApp only supports one media attachment per message.
        Text goes with the first attachment; remaining ones are sent alone."""
        if attachments:
            return [(content, [attachments[0]])] + [("", [a]) for a in attachments[1:]]
        return [(content, [])]

    def _process_attachments(
        self, client: httpx.Client, attachments: list[str]
    ) -> list[AttachmentFile]:
        files: list[AttachmentFile] = []

        for url in attachments:
            filename = url.split("/")[-1]
            response = client.get(url, timeout=30.0)
            response.raise_for_status()
            content_type = magic.from_buffer(response.content, mime=True)
            files.append(("attachments[]", (filename, response.content, content_type)))

        return files
