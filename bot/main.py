import asyncio
import sys
from loguru import logger

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.exceptions import TelegramNetworkError

from bot.config import settings
from bot.dao.database import engine, Base
from bot.infrastructure.database_middleware import DatabaseMiddleware
from bot.adapters.handlers import start_handler, table_handler, expense_handler


async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created successfully")


async def main():    
    await create_tables()
    
    bot = None
    try:
        logger.info("Starting bot...")
        
        bot = Bot(
            token=settings.BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
        
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Dropped pending updates")
        
        dp = Dispatcher(storage=MemoryStorage())
        
        dp.message.middleware(DatabaseMiddleware())
        dp.callback_query.middleware(DatabaseMiddleware())
        
        dp.include_router(start_handler.router)
        dp.include_router(table_handler.router)
        dp.include_router(expense_handler.router)
        
        logger.info("Bot started successfully")
        
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types()
        )

    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
        
    except Exception as e:
        logger.error(f"Unexpected error: {e}. Retrying in {retry_delay} seconds...")
        
    finally:
        if bot:
            try:
                await bot.session.close()
                logger.info("Bot session closed")
            except:
                pass
    
    try:
        await engine.dispose()
        logger.info("Database engine disposed")
    except:
        pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
        sys.exit(0)