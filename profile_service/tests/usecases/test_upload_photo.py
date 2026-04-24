from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest

from profile_service.domain.photo import Photo
from profile_service.usecases.upload_photo.usecase import UploadPhotoUsecase


@pytest.fixture
def profile_repository() -> AsyncMock:
    repo = AsyncMock()

    @asynccontextmanager
    async def _context():
        yield AsyncMock()

    repo.context = _context
    repo.get_profile_by_telegram_id = AsyncMock(return_value=AsyncMock(id=42))
    repo.create_photo = AsyncMock(
        return_value=Photo(
            id=7,
            profile_id=42,
            minio_key="profiles/42/test-key",
        )
    )
    return repo


@pytest.fixture
def storage() -> AsyncMock:
    client = AsyncMock()
    client.put = AsyncMock()
    return client


@pytest.fixture
def message_queue() -> AsyncMock:
    client = AsyncMock()
    client.push = AsyncMock()
    return client


@pytest.mark.asyncio
async def test_upload_photo_publishes_photo_uploaded_event(
    profile_repository: AsyncMock,
    storage: AsyncMock,
    message_queue: AsyncMock,
) -> None:
    usecase = UploadPhotoUsecase(
        profile_repository=profile_repository,
        storage=storage,
        message_queue=message_queue,
    )

    response = await usecase.execute(
        UploadPhotoUsecase.Request(
            telegram_id=1001,
            data=b"binary-image",
            content_type="image/jpeg",
        )
    )

    assert response.photo.id == 7
    message_queue.push.assert_awaited_once()
    routing_key, push_message = message_queue.push.await_args.args
    assert routing_key == "photo.uploaded"
    assert b'"photo_id": 7' in push_message.body
    assert b'"profile_id": 42' in push_message.body
    assert push_message.content_type == "application/json"
