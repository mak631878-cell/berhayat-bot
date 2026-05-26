"""
app/services/notify.py — уведомления владельцу о новом кандидате
"""
from __future__ import annotations

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from app.models.db import Employee


class NotifyService:
    def __init__(self, bot: Bot, owner_id: int):
        self.bot = bot
        self.owner_id = owner_id

    async def send_accreditation_request(self, emp: Employee) -> None:
        """Отправляет карточку кандидата владельцу с кнопками Принять/Отклонить."""
        text = (
            f"📥 <b>Новая заявка на аккредитацию</b>\n\n"
            f"👤 ФИО: {emp.fio}\n"
            f"📌 Должность: {emp.position}\n"
            f"📅 Дата рождения: {emp.birth_date.strftime('%d.%m.%Y') if emp.birth_date else '—'}\n"
            f"🏙 Город: {emp.city or '—'}\n"
            f"📞 Телефон: {emp.phone or '—'}\n"
            f"🎓 Образование: {emp.education or '—'}"
        )

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Принять", callback_data=f"approve_{emp.id}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{emp.id}"),
            ]
        ])

        # Если есть фото — отправляем с фото
        if emp.photo_url:
            await self.bot.send_photo(
                chat_id=self.owner_id,
                photo=emp.photo_url,
                caption=text,
                reply_markup=kb,
                parse_mode="HTML",
            )
        else:
            await self.bot.send_message(
                chat_id=self.owner_id,
                text=text,
                reply_markup=kb,
                parse_mode="HTML",
            )
