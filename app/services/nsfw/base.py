from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ModerationResult:
    is_safe: bool
    flagged_categories: list[str] = field(default_factory=list)


class BaseNSFWFilter(ABC):
    @abstractmethod
    async def is_safe_text(self, text: str) -> ModerationResult: ...

    @abstractmethod
    async def is_safe_image(self, image_url: str) -> ModerationResult: ...
