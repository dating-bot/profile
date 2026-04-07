from dataclasses import dataclass
from typing import final, override

import aio_pika
import structlog

from profile_service.infra.rabbitmq_topology import PROFILE_EXCHANGE_NAME, RabbitMQTopology
from profile_service.protocols.events.protocol import EventPublisherProtocol

log = structlog.stdlib.get_logger("profile_service.adapters.events.rabbitmq")


@final
@dataclass(slots=True)
class RabbitMQEventPublisherAdapter(EventPublisherProtocol):
    _topology: RabbitMQTopology

    @override
    async def publish(self, request: EventPublisherProtocol.PublishRequest) -> None:
        exchange = self._topology.exchanges.get(PROFILE_EXCHANGE_NAME)
        if exchange is None:
            log.error("exchange not found", exchange=PROFILE_EXCHANGE_NAME)
            return

        message = aio_pika.Message(
            body=request.payload,
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        )
        await exchange.publish(message, routing_key=request.routing_key)
        log.debug("event published", routing_key=request.routing_key)
