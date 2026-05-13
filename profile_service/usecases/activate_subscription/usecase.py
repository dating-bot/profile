from dataclasses import dataclass
from typing import final

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from profile_service.domain.profile import Profile, SubscriptionTier
from profile_service.protocols.events.protocol import MessageQueueProtocol
from profile_service.protocols.profile.repository import ProfileRepositoryProtocol
from profile_service.usecases._profile_events import publish_profile_updated

log = structlog.stdlib.get_logger("profile_service.usecases.ActivateSubscriptionUsecase")


class ActivateSubscriptionNotFoundError(Exception):
    """No profile for telegram_id."""


@final
class ActivateSubscriptionUsecase:
    def __init__(
        self,
        *,
        profile_repository: ProfileRepositoryProtocol[AsyncSession],
        message_queue: MessageQueueProtocol,
    ) -> None:
        self._profile_repository = profile_repository
        self._message_queue = message_queue

    @dataclass
    class Request:
        telegram_id: int
        tier: SubscriptionTier
        duration_seconds: int
        telegram_payment_charge_id: str | None = None
        provider_payment_charge_id: str | None = None
        invoice_payload: str | None = None

    @dataclass
    class Response:
        profile: Profile

    async def execute(self, request: Request) -> Response:
        try:
            async with self._profile_repository.context() as session:
                profile = await self._profile_repository.activate_subscription(
                    session=session,
                    request=ProfileRepositoryProtocol.ActivateSubscriptionRequest(
                        telegram_id=request.telegram_id,
                        tier=request.tier,
                        duration_seconds=request.duration_seconds,
                        telegram_payment_charge_id=request.telegram_payment_charge_id,
                        provider_payment_charge_id=request.provider_payment_charge_id,
                        invoice_payload=request.invoice_payload,
                    ),
                )
        except ValueError as e:
            raise ActivateSubscriptionNotFoundError(str(e)) from e

        await publish_profile_updated(
            self._message_queue,
            profile_id=profile.id,
            telegram_id=request.telegram_id,
        )
        log.info(
            "subscription activated",
            telegram_id=request.telegram_id,
            tier=request.tier.value,
            subscription_expires_at=profile.subscription_expires_at.isoformat()
            if profile.subscription_expires_at
            else None,
        )
        return self.Response(profile=profile)
