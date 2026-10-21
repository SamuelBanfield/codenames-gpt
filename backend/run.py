import asyncio
import logging
from codenames.app import main

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, force=True)
    logging.info("Starting Codenames GPT server...")
    asyncio.run(main())
