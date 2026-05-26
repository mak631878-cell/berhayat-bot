"""
app/services/invite.py — генерация и проверка invite-токенов
"""
from __future__ import annotations

import secrets
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

import redis.asyncio as aioredis
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import Employee, RoleName

logger = logging.getLogger(__name__)

TOKEN_PREFIX = "invite:"
DEFAULT_TTL  = 7 * 24 * 3600  # 7 дней в секундах


class InviteService:
    def __init__(self, redis: aioredis.Redis, ttl: int = DEFAULT_TTL):
        self.redis = redis
        self.ttl = ttl

    # ── Создание приглашения (только владелец) ──────────────────────────

    async def create_invite(
        self,
        db: AsyncSession,
        owner: Employee,
        position: str,
    ) -> str:
        """
        Генерирует уникальный токен, сохраняет в Redis и БД.
        Возвращает токен (без префикса).
        """
        token = secrets.token_urlsafe(32)

        # Сохраняем в Redis: ключ → JSON с метаданными
        import json
        payload = json.dumps({
            "position": position,
            "invited_by": owner.id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        await self.redis.setex(f"{TOKEN_PREFIX}{token}", self.ttl, payload)

        # Создаём «пустую» запись сотрудника с токеном
        stub = Employee(
            fio=f"[ожидает регистрации] {position}",
            position=position,
            invite_token=token,
            invited_by=owner.id,
            is_active=False,
            role=RoleName.sales,
        )
        db.add(stub)
        await db.commit()
        await db.refresh(stub)

        logger.info("Invite created: token=%s, position=%s, by=%s", token, position, owner.id)
        return token

    # ── Проверка токена ─────────────────────────────────────────────────

    async def validate_token(self, token: str) -> Optional[dict]:
        """
        Проверяет токен в Redis.
        Возвращает payload (dict) или None если просрочен/не найден.
        """
        import json
        raw = await self.redis.get(f"{TOKEN_PREFIX}{token}")
        if raw is None:
            return None
        return json.loads(raw)

    async def consume_token(self, token: str) -> None:
        """Удаляет токен из Redis (одноразовое использование)."""
        await self.redis.delete(f"{TOKEN_PREFIX}{token}")

    # ── Финализация регистрации ─────────────────────────────────────────

    async def finalize_registration(
        self,
        db: AsyncSession,
        token: str,
        telegram_id: int,
        fio: str,
        birth_date,
        city: str,
        phone: str,
        education: str,
        photo_url: str,
    ) -> Optional[Employee]:
        """
        Заполняет данные сотрудника и помечает is_active=False
        (ждёт подтверждения владельцем).
        """
        result = await db.execute(
            select(Employee).where(Employee.invite_token == token)
        )
        emp = result.scalar_one_or_none()
        if emp is None:
            return None

        emp.telegram_id  = telegram_id
        emp.fio          = fio
        emp.birth_date   = birth_date
        emp.city         = city
        emp.phone        = phone
        emp.education    = education
        emp.photo_url    = photo_url
        emp.consent_pd   = True
        emp.is_active    = False  # Ждём одобрения

        await db.commit()
        await db.refresh(emp)
        return emp

    async def approve_employee(
        self,
        db: AsyncSession,
        employee_id: int,
    ) -> Optional[Employee]:
        """Владелец одобрил — активируем сотрудника."""
        result = await db.execute(
            select(Employee).where(Employee.id == employee_id)
        )
        emp = result.scalar_one_or_none()
        if emp:
            emp.is_active    = True
            emp.invite_token = None  # Очищаем использованный токен
            await db.commit()
            await db.refresh(emp)
        return emp

    async def reject_employee(
        self,
        db: AsyncSession,
        employee_id: int,
    ) -> None:
        """Владелец отклонил — удаляем заглушку."""
        result = await db.execute(
            select(Employee).where(Employee.id == employee_id)
        )
        emp = result.scalar_one_or_none()
        if emp:
            await db.delete(emp)
            await db.commit()
