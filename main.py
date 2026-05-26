"""
main.py — точка входа бота БЕРХАЯТ
"""
from __future__ import annotations

import asyncio
import logging
import os

import redis.asyncio as aioredis
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.handlers import registration, start, cabinet, documents, menu
from app.middlewares.role_access import RoleAccessMiddleware
from app.models.db import Base
from app.services.document import DocumentService, StorageService
from app.services.invite import InviteService
from app.services.notify import NotifyService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    # ── Конфиг из env ────────────────────────────────────────
    BOT_TOKEN      = os.environ["BOT_TOKEN"]
    OWNER_ID       = int(os.environ["OWNER_TELEGRAM_ID"])
    DATABASE_URL   = os.environ["DATABASE_URL"]
    REDIS_URL      = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    INVITE_TTL     = int(os.environ.get("INVITE_TOKEN_TTL", 604800))

    S3_ENDPOINT    = os.environ.get("S3_ENDPOINT", "https://storage.yandexcloud.net")
    S3_BUCKET      = os.environ.get("S3_BUCKET", "berhayat-docs")
    AWS_KEY_ID     = os.environ.get("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET     = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
    S3_REGION      = os.environ.get("S3_REGION", "ru-central1")

    # ── База данных ──────────────────────────────────────────
    engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # ── Redis + FSM-хранилище ────────────────────────────────
    redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)
    storage = RedisStorage(redis=redis_client)

    # ── Сервисы ──────────────────────────────────────────────
    invite_svc  = InviteService(redis=redis_client, ttl=INVITE_TTL)
    storage_svc = StorageService(S3_ENDPOINT, S3_BUCKET, AWS_KEY_ID, AWS_SECRET, S3_REGION)
    doc_svc     = DocumentService(storage=storage_svc)

    # ── Bot + Dispatcher ─────────────────────────────────────
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    notify_svc = NotifyService(bot=bot, owner_id=OWNER_ID)

    dp = Dispatcher(storage=storage)

    # ── Middleware ───────────────────────────────────────────
    # Инжектируем сессию в каждый апдейт
    async def db_session_middleware(handler, event, data):
        async with async_session() as session:
            data["session"] = session
            return await handler(event, data)

    dp.update.outer_middleware(db_session_middleware)
    dp.update.outer_middleware(RoleAccessMiddleware())

    # ── Инжекция зависимостей через workflow_data ────────────
    dp["invite_service"]  = invite_svc
    dp["notify_service"]  = notify_svc
    dp["doc_service"]     = doc_svc
    dp["storage"]         = storage_svc

    # ── Роутеры ──────────────────────────────────────────────
    dp.include_router(registration.router)
    dp.include_router(start.router)
    dp.include_router(menu.router)       # главное меню — кнопки
    dp.include_router(cabinet.router)
    dp.include_router(documents.router)

    logger.info("🤖 Бот БЕРХАЯТ запущен (owner_id=%d)", OWNER_ID)

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()
        await redis_client.close()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
