import json
from uuid import uuid4

import structlog.contextvars

from profile_service.protocols.events.protocol import MessageQueueProtocol, PushMessage

PROFILE_UPDATED_ROUTING_KEY = "profile.updated"


async def publish_profile_updated(
    message_queue: MessageQueueProtocol,
    *,
    profile_id: int,
    telegram_id: int,
) -> None:
    trace_id = str(structlog.contextvars.get_contextvars().get("trace_id") or uuid4().hex)
    _ = await message_queue.push(
        PROFILE_UPDATED_ROUTING_KEY,
        PushMessage(
            body=json.dumps({"profile_id": profile_id, "telegram_id": telegram_id}).encode(),
            headers={"trace_id": trace_id},
            content_type="application/json",
        ),
    )
