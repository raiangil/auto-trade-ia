import asyncio
from src.core.database import DatabaseSession
from src.core.services import DatasetRepository, BotEngineService
from datetime import datetime
import json

async def main():  
  bot_service = BotEngineService()
  await bot_service.run_loop()
  # indicators = await bot_service.run_cycle("BTCUSDT", None, "1h")
if __name__ == "__main__":
  asyncio.run(main())