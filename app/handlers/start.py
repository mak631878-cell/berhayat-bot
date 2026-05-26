"""
app/handlers/start.py

/add_position — владелец создаёт должность + invite-ссылку
/approve_<id> / /reject_<id> — владелец одобряет/отклоняет кандидата
"""
from __future__ import annotations

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from sqlalchemy.ext.asyncio import AsyncSession

from app.middlewares.role_access import RoleFilter
from app.models.db import Employee, RoleName
from app.services.invite import InviteService
from app.utils.states import AddPositionFSM

router = Router(name="start")


# ──────────────────────────────────────────────────────────────────────────────
# /add_position — только для владельца
# ──────────────────────────────────────────────────────────────────────────────

@router.message(
    Command("add_position"),
    RoleFilter("owner"),
)
async def cmd_add_position(message: Message, state: FSMContext):
    await state.set_state(AddPositionFSM.waiting_position_name)
    await message.answer(
        "📋 Введите <b>название должности</b> для нового сотрудника:\n"
        "<i>Например: Старший менеджер по продажам</i>",
        parse_mode="HTML",
    )


@router.message(AddPositionFSM.waiting_position_name)
async def cmd_add_position_name(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    invite_service: InviteService,
    employee: Employee,
):
    position = (message.text or "").strip()
    if len(position) < 3:
        await message.answer("⚠️ Название должности слишком короткое.")
        return

    token = await invite_service.create_invite(
        db=session,
        owner=employee,
        position=position,
    )

    bot_username = (await message.bot.get_me()).username
    invite_link = f"https://t.me/{bot_username}?start=invite_{token}"

    await message.answer(
        f"✅ Приглашение создано!\n\n"
        f"📌 Должность: <b>{position}</b>\n"
        f"🔗 Ссылка (действует 7 дней):\n<code>{invite_link}</code>\n\n"
        f"⚠️ Ссылка одноразовая — после регистрации аннулируется.",
        parse_mode="HTML",
    )
    await state.clear()


# ──────────────────────────────────────────────────────────────────────────────
# Одобрение / отклонение (callback от уведомления владельцу)
# ──────────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("approve_"))
async def cb_approve(
    callback: CallbackQuery,
    session: AsyncSession,
    invite_service: InviteService,
    employee: Employee,
):
    if employee.role != RoleName.owner:
        await callback.answer("🚫 Нет прав", show_alert=True)
        return

    emp_id = int(callback.data.split("_")[1])
    approved = await invite_service.approve_employee(session, emp_id)

    if approved is None:
        await callback.answer("❌ Сотрудник не найден", show_alert=True)
        return

    # Уведомляем сотрудника
    await callback.bot.send_message(
        chat_id=approved.telegram_id,
        text=(
            f"🎉 Ваша аккредитация одобрена!\n"
            f"Должность: <b>{approved.position}</b>\n\n"
            f"Используйте /my_cabinet для входа в личный кабинет."
        ),
        parse_mode="HTML",
    )

    await callback.message.edit_text(
        callback.message.text + f"\n\n✅ <b>Принят:</b> {approved.fio}",
        parse_mode="HTML",
        reply_markup=None,
    )
    await callback.answer("✅ Сотрудник принят!")


@router.callback_query(F.data.startswith("reject_"))
async def cb_reject(
    callback: CallbackQuery,
    session: AsyncSession,
    invite_service: InviteService,
    employee: Employee,
):
    if employee.role != RoleName.owner:
        await callback.answer("🚫 Нет прав", show_alert=True)
        return

    emp_id = int(callback.data.split("_")[1])

    # Достаём telegram_id до удаления
    from sqlalchemy import select
    result = await session.execute(
        select(Employee).where(Employee.id == emp_id)
    )
    candidate = result.scalar_one_or_none()
    tg_id = candidate.telegram_id if candidate else None

    await invite_service.reject_employee(session, emp_id)

    if tg_id:
        await callback.bot.send_message(
            chat_id=tg_id,
            text="❌ К сожалению, ваша заявка на аккредитацию отклонена.\nСвяжитесь с владельцем для уточнения.",
        )

    await callback.message.edit_text(
        callback.message.text + "\n\n❌ <b>Отклонён</b>",
        parse_mode="HTML",
        reply_markup=None,
    )
    await callback.answer("Отклонено.")
