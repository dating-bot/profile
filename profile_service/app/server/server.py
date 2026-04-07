import asyncio
import signal

import grpclib.server
import structlog

from profile_service import infra
from profile_service.app.server import di
from profile_service.app.server.grpc_handler import ProfileServiceHandler
from profile_service.app.server.health import create_health_service
from profile_service.app.server.utils import configure_logger

log = structlog.stdlib.get_logger("profile_service.server")


async def run_grpc_server(
    handler: ProfileServiceHandler,
    config: infra.GrpcServerConfig,
) -> None:
    server = grpclib.server.Server([handler, create_health_service()])
    await server.start(config.host, config.port)
    log.info("gRPC server started", host=config.host, port=config.port)

    try:
        await server.wait_closed()
    except asyncio.CancelledError:
        log.info("gRPC server cancelled, shutting down")
        server.close()
        await server.wait_closed()


async def main() -> None:
    config = await di.container.get(infra.GlobalConfig)

    configure_logger(
        json_mode=False,
        log_level="DEBUG" if config.debug else "INFO",
    )
    log.info("Starting profile-service")

    grpc_handler_instance = await di.container.get(ProfileServiceHandler)
    grpc_config = await di.container.get(infra.GrpcServerConfig)

    # Ensure MinIO bucket exists on startup.
    from profile_service.protocols.storage.protocol import StorageProtocol  # noqa: PLC0415

    storage = await di.container.get(StorageProtocol)
    await storage.ensure_bucket()

    shutdown_event = asyncio.Event()

    def signal_handler() -> None:
        log.info("Shutdown signal received, stopping server")
        shutdown_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)

    grpc_task = asyncio.create_task(run_grpc_server(grpc_handler_instance, grpc_config))

    log.info("Server started successfully")

    try:
        _ = await shutdown_event.wait()
    except KeyboardInterrupt:
        log.info("Keyboard interrupt received")
    finally:
        log.info("Stopping server")
        _ = grpc_task.cancel()
        _ = await asyncio.gather(grpc_task, return_exceptions=True)
        await di.container.close()
        log.info("Server stopped")


if __name__ == "__main__":
    asyncio.run(main())
