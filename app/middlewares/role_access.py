"""
app/middlewares/role_access.py

Middleware проверяет:
  1. Является ли пользователь зарегистрированным активным сотрудником.
  2. Имеет ли нужную роль для текущего handler-а (через флаг required_roles).

Использование в хэндлере:
    router = Router()
    router.message.filter(RoleFilter("owner"))   # только владелец

Или через декоратор флага на роутере:
    router.message.middleware(RoleAccessMiddleware())

Каждый обработанный апдейт логируется в таблицу logs.
"""
from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Optional

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import Employee, RoleName, Log

logger = logging.getLogger(__name__)

# Действия, разрешённые без аккаунта (регистрация через invite)
PUBLIC_COMMANDS = {"/start"}


class RoleAccessMiddleware(BaseMiddleware):
    """
    Outer middleware — навешивается на диспетчер глобально.

    Добавляет в data["employee"] объект Employee (или None).
    Если пользователь не активен — блокирует апдейт (кроме /start).
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        session: AsyncSession = data.get("session")

        # Определяем telegram_id
        tg_id: Optional[int] = None
        text: Optional[str] = None

        if isinstance(event, Message):
            tg_id = event.from_user.id if event.from_user else None
            text = event.text or ""
        elif isinstance(event, CallbackQuery):
            tg_id = event.from_user.id if event.from_user else None

        # Пропускаем системные апдейты без пользователя
        if tg_id is None:
            return await handler(event, data)

        # Ищем сотрудника
        employee: Optional[Employee] = None
        if session:
            result = await session.execute(
                select(Employee).where(Employee.telegram_id == tg_id)
            )
            employee = result.scalar_one_or_none()

        data["employee"] = employee

        # Публичные команды — пропускаем без проверки
        if text and any(text.startswith(cmd) for cmd in PUBLIC_COMMANDS):
            return await handler(event, data)

        # Проверяем активность
        if employee is None or not employee.is_active:
            if isinstance(event, Message):
                await event.answer(
                    "⛔ У вас нет доступа к боту.\n"
                    "Обратитесь к владельцу или воспользуйтесь ссылкой-приглашением."
                )
            elif isinstance(event, CallbackQuery):
                await event.answer("⛔ Нет доступа", show_alert=True)
            return  # Блокируем дальнейшую обработку

        # Логируем действие
        if session and employee:
            action = text or (
                event.data if isinstance(event, CallbackQuery) else "unknown"
            )
            session.add(Log(
                employee_id=employee.id,
                action=action[:200],
            ))
            # Не делаем await commit здесь — сессия закроется после хэндлера

        return await handler(event, data)


class RoleFilter:
    """
    Фильтр для конкретного роутера/хэндлера.

    Пример:
        @router.message(Command("add_position"), RoleFilter("owner"))
        async def add_position_handler(message: Message, employee: Employee):
            ...
    """

    def __init__(self, *roles: str):
        self.roles = {RoleName(r) for r in roles}

    async def __call__(
        self,
        event: Message | CallbackQuery,
        employee: Optional[Employee] = None,
    ) -> bool:
        if employee is None:
            return False
        if employee.role not in self.roles:
            if isinstance(event, Message):
                await event.answer("🚫 Недостаточно прав для этого действия.")
            elif isinstance(event, CallbackQuery):
                await event.answer("🚫 Нет прав", show_alert=True)
            return False
        return True
