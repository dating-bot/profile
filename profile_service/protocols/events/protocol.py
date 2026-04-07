from dataclasses import dataclass
from typing import Protocol


class EventPublisherProtocol(Protocol):
    @dataclass
    class PublishRequest:
        routing_key: str
        payload: bytes

    async def publish(self, request: PublishRequest) -> None: ...
