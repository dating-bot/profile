import asyncio

from profile_service.app.server import server

if __name__ == "__main__":
    asyncio.run(server.main())
