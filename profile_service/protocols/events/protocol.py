from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import final, override

from pamqp.common import FieldValue


class MessageQueueError(Exception): ...


class MessageQueueConnectionError(MessageQueueError):
    """Raised when connection to message queue fails."""


class MessageQueueTimeoutError(MessageQueueError):
    """Raised when timeout occurs while waiting for messages."""


class MessageQueueChannelError(MessageQueueError):
    """Raised when channel operation fails."""


@final
@dataclass(slots=True, repr=False)
class Message:
    body: bytes
    delivery_tag: object
    routing_key: str
    exchange: str
    headers: dict[str, object] | None = None
    content_type: str | None = None
    content_encoding: str | None = None

    def __post_init__(self) -> None:
        self.headers = self.headers or {}

    def decode(self, encoding: str = "utf-8") -> str:
        return self.body.decode(encoding)

    @override
    def __repr__(self) -> str:
        return f"Message(routing_key={self.routing_key!r}, exchange={self.exchange!r}, body_size={len(self.body)})"


@final
@dataclass(slots=True)
class PushMessage:
    body: bytes
    headers: dict[str, FieldValue] | None = None
    content_type: str | None = None
    content_encoding: str | None = None


class MessageQueueProtocol(ABC):
    @abstractmethod
    async def pull(
        self,
        queue_name: str,
        *,
        prefetch_count: int = 1,
        auto_ack: bool = False,
    ) -> AsyncGenerator[Message]:
        ...
        yield  # type: ignore[misc]  # pyright: ignore[reportReturnType]

    @abstractmethod
    async def ack(self, message: Message) -> None: ...

    @abstractmethod
    async def nack(self, message: Message, *, requeue: bool = True) -> None: ...

    @abstractmethod
    async def reject(self, message: Message, *, requeue: bool = False) -> None: ...

    @abstractmethod
    async def push(self, queue_name: str, message: PushMessage) -> None: ...
