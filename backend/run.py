import asyncio
import logging
import codenames.websocket_server as websocket_server

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, force=True)
    logging.info("Starting Codenames GPT server...")
    asyncio.run(websocket_server.main())