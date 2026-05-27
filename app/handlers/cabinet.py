"""
app/handlers/cabinet.py — /my_cabinet
"""
from __future__ import annotations

from datetime import date

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import Employee, Deal, Shift, Document, RoleName

router = Router(name="cabinet")


@router.message(Command("my_cabinet"))
async def cmd_my_cabinet(
    message: Message,
    session: AsyncSession,
    employee: Employee,
):
    # ── Статус смены ─────────────────────────────────────────
    today = date.today()
    shift_result = await session.execute(
        select(Shift).where(
            Shift.employee_id == employee.id,
            Shift.date == today,
        )
    )
    shift = shift_result.scalar_one_or_none()
    on_shift = shift.is_on_shift if shift else False
    shift_icon = "🟢 На смене" if on_shift else "🔴 Не на смене"

    # ── Статистика сделок (для менеджеров) ───────────────────
    deals_text = ""
    if employee.role in (RoleName.sales,):
        total_count = await session.scalar(
            select(func.count(Deal.id)).where(Deal.employee_id == employee.id)
        )
        total_sum = await session.scalar(
            select(func.sum(Deal.amount)).where(Deal.employee_id == employee.id)
        ) or 0
        won_count = await session.scalar(
            select(func.count(Deal.id)).where(
                Deal.employee_id == employee.id,
                Deal.status == "won",
            )
        )
        deals_text = (
            f"\n\n📊 <b>Моя статистика:</b>\n"
            f"├ Всего сделок: {total_count}\n"
            f"├ Выиграно: {won_count}\n"
            f"└ Общая сумма: {total_sum:,.0f} ₸"
        )

    # ── Зарплата (скрыта от управляющих) ─────────────────────
    salary_line = ""
    if employee.salary is not None:
        salary_line = f"\n💰 <b>Зарплата:</b> {employee.salary:,.0f} ₸"

    role_map = {
        RoleName.owner:    "👑 Владелец",
        RoleName.manager_: "🔧 Управляющий",
        RoleName.sales:    "💼 Менеджер по продажам",
    }

    text = (
        f"👤 <b>Личный кабинет</b>\n\n"
        f"ФИО: <b>{employee.fio}</b>\n"
        f"Должность: {employee.position or '—'}\n"
        f"Роль: {role_map.get(employee.role, employee.role)}\n"
        f"Статус: {shift_icon}"
        f"{salary_line}"
        f"{deals_text}"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🟢 Выйти на смену" if not on_shift else "🔴 Уйти со смены",
                callback_data="shift_toggle",
            )
        ],
        [
            InlineKeyboardButton(text="📄 Мои документы", callback_data="my_docs"),
        ],
    ])

    await message.answer(text, reply_markup=kb, parse_mode="HTML")


# ── Переключение смены ────────────────────────────────────────────────────────

from aiogram import F
from aiogram.types import CallbackQuery


@router.callback_query(F.data == "shift_toggle")
async def cb_shift_toggle(
    callback: CallbackQuery,
    session: AsyncSession,
    employee: Employee,
):
    today = date.today()
    result = await session.execute(
        select(Shift).where(
            Shift.employee_id == employee.id,
            Shift.date == today,
        )
    )
    shift = result.scalar_one_or_none()

    if shift is None:
        shift = Shift(employee_id=employee.id, date=today, is_on_shift=True)
        session.add(shift)
        new_status = True
    else:
        shift.is_on_shift = not shift.is_on_shift
        new_status = shift.is_on_shift

    await session.commit()

    status_text = "🟢 Вы на смене" if new_status else "🔴 Вы ушли со смены"
    await callback.answer(status_text)
    await callback.message.edit_reply_markup(
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🟢 Выйти на смену" if not new_status else "🔴 Уйти со смены",
                    callback_data="shift_toggle",
                )
            ],
            [InlineKeyboardButton(text="📄 Мои документы", callback_data="my_docs")],
        ])
    )


@router.callback_query(F.data == "my_docs")
async def cb_my_docs(
    callback: CallbackQuery,
    session: AsyncSession,
    employee: Employee,
):
    from sqlalchemy.orm import joinedload

    result = await session.execute(
        select(Document)
        .join(Deal)
        .where(Deal.employee_id == employee.id)
        .order_by(Document.created_at.desc())
        .limit(10)
        .options(joinedload(Document.deal))
    )
    docs = result.scalars().all()

    if not docs:
        await callback.answer("У вас пока нет документов.", show_alert=True)
        return

    type_emoji = {
        "contract": "📑",
        "act": "📋",
        "commercial": "📨",
        "invoice": "🧾",
    }

    lines = [f"📄 <b>Мои документы (последние 10):</b>\n"]
    for d in docs:
        lines.append(
            f"{type_emoji.get(d.type, '📄')} {d.type.upper()} "
            f"— {d.created_at.strftime('%d.%m.%Y')}\n"
            f"   <a href='{d.file_url}'>Скачать</a>"
        )

    await callback.message.answer(
        "\n".join(lines),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
    await callback.answer()
