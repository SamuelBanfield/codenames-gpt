import asyncio
import logging
import codenames.websocket_server as websocket_server

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(websocket_server.main())