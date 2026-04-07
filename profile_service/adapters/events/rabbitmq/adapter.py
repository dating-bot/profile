from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import final, override

import aio_pika
import aio_pika.abc
import structlog

from profile_service.infra.rabbitmq_topology import RabbitMQTopology
from profile_service.protocols.events.protocol import (
    Message,
    MessageQueueChannelError,
    MessageQueueError,
    MessageQueueProtocol,
    MessageQueueTimeoutError,
    PushMessage,
)

log = structlog.stdlib.get_logger("profile_service.adapters.RabbitMQAdapter")


@final
@dataclass(slots=True)
class RabbitMQAdapter(MessageQueueProtocol):
    _topology: RabbitMQTopology
    _message_refs: dict[object, aio_pika.abc.AbstractIncomingMessage] = field(default_factory=dict, init=False)

    @override
    async def pull(
        self,
        queue_name: str,
        *,
        prefetch_count: int = 1,
        auto_ack: bool = False,
    ) -> AsyncGenerator[Message]:
        queue = self._topology.get_for_consuming(queue_name)
        if queue is None:
            msg = (
                f"Queue {queue_name} was not declared for consuming "
                "(it either does not exist or was declared as a destination)"
            )
            raise MessageQueueError(msg)

        channel = self._topology.get_channel(queue_name)
        if channel is None or channel.is_closed:
            msg = f"channel is not opened for queue {queue_name}"
            raise MessageQueueChannelError(msg)

        try:
            _ = await channel.set_qos(prefetch_count=prefetch_count)
            async with queue.iterator() as queue_iter:
                async for incoming_message in queue_iter:
                    message = self._to_message(incoming_message)
                    if auto_ack:
                        try:
                            async with incoming_message.process(ignore_processed=True):
                                yield message
                        except aio_pika.exceptions.MessageProcessError as e:
                            log.warning("message process error, skipping", error=str(e))
                        finally:
                            _ = self._message_refs.pop(message.delivery_tag, None)
                    else:
                        yield message
        except aio_pika.exceptions.ChannelClosed as e:
            raise MessageQueueChannelError("Channel closed: " + str(e)) from e
        except aio_pika.exceptions.QueueEmpty as e:
            raise MessageQueueTimeoutError("Queue empty: " + str(e)) from e
        except Exception as e:
            raise MessageQueueError("Error pulling messages: " + str(e)) from e

    @override
    async def ack(self, message: Message) -> None:
        ref = self._get_aio_pika_ref(message)
        try:
            await ref.ack()
        finally:
            _ = self._message_refs.pop(message.delivery_tag, None)

    @override
    async def nack(self, message: Message, *, requeue: bool = True) -> None:
        ref = self._get_aio_pika_ref(message)
        try:
            await ref.nack(requeue=requeue)
        finally:
            _ = self._message_refs.pop(message.delivery_tag, None)

    @override
    async def reject(self, message: Message, *, requeue: bool = False) -> None:
        ref = self._get_aio_pika_ref(message)
        try:
            await ref.reject(requeue=requeue)
        finally:
            _ = self._message_refs.pop(message.delivery_tag, None)

    @override
    async def push(self, queue_name: str, message: PushMessage) -> None:
        exchange = self._topology.get_for_publishing(queue_name)
        if exchange is None:
            msg = f"Queue {queue_name} was not declared for pushing"
            raise MessageQueueError(msg)

        channel = self._topology.get_channel(queue_name)
        if channel is None or channel.is_closed:
            msg = f"channel is not opened for queue {queue_name}"
            raise MessageQueueChannelError(msg)

        try:
            push_msg = aio_pika.Message(
                body=message.body,
                headers=message.headers or None,
                content_type=message.content_type,
                content_encoding=message.content_encoding,
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            )
            _ = await exchange.publish(message=push_msg, routing_key=queue_name)
        except aio_pika.exceptions.ChannelClosed as e:
            raise MessageQueueChannelError("Channel closed: " + str(e)) from e
        except Exception as e:
            raise MessageQueueError("Error publishing message: " + str(e)) from e

    def _to_message(self, incoming: aio_pika.abc.AbstractIncomingMessage) -> Message:
        msg = Message(
            body=incoming.body,
            delivery_tag=incoming.delivery_tag,
            routing_key=incoming.routing_key or "",
            exchange=incoming.exchange or "",
            headers=dict(incoming.headers) if incoming.headers else None,
            content_type=incoming.content_type,
            content_encoding=incoming.content_encoding,
        )
        self._message_refs[msg.delivery_tag] = incoming
        return msg

    def _get_aio_pika_ref(self, message: Message) -> aio_pika.abc.AbstractIncomingMessage:
        ref = self._message_refs.get(message.delivery_tag)
        if ref is None:
            raise MessageQueueChannelError("Invalid message: missing internal reference")
        return ref
