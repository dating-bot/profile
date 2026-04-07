from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Literal

import aio_pika
from aio_pika import ExchangeType


@dataclass(slots=True, frozen=True)
class Exchange:
    name: str
    type: aio_pika.ExchangeType | None = None
    declare: bool = False
    ensure: bool = True
    durable: Literal[True] = True
    auto_delete: bool = False
    internal: bool = False


@dataclass(slots=True, frozen=True)
class Queue:
    name: str
    declare: bool = True
    ensure: bool = True
    durable: bool = True
    exclusive: bool = False
    auto_delete: bool = False


@dataclass(slots=True)
class RabbitMQTopologyConfig:
    publish: dict[Exchange, list[Queue]]
    consume: dict[Queue, Exchange | None]


@dataclass(slots=True)
class RabbitMQTopology:
    exchanges: dict[str, aio_pika.abc.AbstractExchange]
    queues: dict[str, aio_pika.abc.AbstractQueue]
    channels: dict[str, aio_pika.abc.AbstractChannel]
    publish: dict[str, list[str]]
    consume: dict[str, str | None]

    def get_for_publishing(self, queue: str) -> aio_pika.abc.AbstractExchange | None:
        exchange_name = next(
            (exchange for exchange, queues in self.publish.items() if queue in queues),
            None,
        )
        if exchange_name is None:
            return None
        return self.exchanges.get(exchange_name, None)

    def get_channel(self, queue: str) -> aio_pika.abc.AbstractChannel | None:
        return self.channels.get(queue, None)


PROFILE_EXCHANGE_NAME = "profile_exchange"
PROFILE_UPDATED_QUEUE = "profile.updated"

TOPOLOGY_CONFIG = RabbitMQTopologyConfig(
    publish={
        Exchange(PROFILE_EXCHANGE_NAME, ExchangeType.TOPIC, declare=True): [
            Queue(PROFILE_UPDATED_QUEUE, declare=True),
        ],
    },
    consume={},
)


async def provide_rabbitmq_topology(
    connection: aio_pika.abc.AbstractRobustConnection,
) -> AsyncGenerator[RabbitMQTopology]:
    exchanges: dict[str, aio_pika.abc.AbstractExchange] = {}
    queues: dict[str, aio_pika.abc.AbstractQueue] = {}
    channels: dict[str, aio_pika.abc.AbstractChannel] = {}
    publish: dict[str, list[str]] = {}
    consume: dict[str, str | None] = {}

    try:
        for exchange, exchange_queues in TOPOLOGY_CONFIG.publish.items():
            per_exchange_channel = await connection.channel()

            if exchange.declare:
                e = await per_exchange_channel.declare_exchange(
                    exchange.name,
                    type=exchange.type or ExchangeType.DIRECT,
                    durable=exchange.durable,
                    auto_delete=exchange.auto_delete,
                    internal=exchange.internal,
                    passive=not exchange.ensure,
                )
            else:
                e = await per_exchange_channel.get_exchange(exchange.name, ensure=exchange.ensure)
            exchanges[exchange.name] = e

            for queue in exchange_queues:
                if queue.declare:
                    q = await per_exchange_channel.declare_queue(
                        queue.name,
                        durable=queue.durable,
                        exclusive=queue.exclusive,
                        auto_delete=queue.auto_delete,
                        passive=not queue.ensure,
                    )
                else:
                    q = await per_exchange_channel.get_queue(queue.name, ensure=queue.ensure)

                queues[queue.name] = q
                _ = await q.bind(e, routing_key=queue.name)
                publish[exchange.name] = [*publish.get(exchange.name, []), queue.name]
                channels[queue.name] = per_exchange_channel

        yield RabbitMQTopology(exchanges, queues, channels, publish, consume)
    finally:
        for channel in channels.values():
            if not channel.is_closed:
                await channel.close()
