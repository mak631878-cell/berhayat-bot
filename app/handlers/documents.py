"""
app/handlers/documents.py — /create_commercial, /create_invoice
"""
from __future__ import annotations

import io
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    BufferedInputFile,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.middlewares.role_access import RoleFilter
from app.models.db import Client, Deal, DealStatus, Document, DocType, Service, Employee
from app.services.document import DocumentService
from app.utils.states import CreateDocFSM

router = Router(name="documents")


# ──────────────────────────────────────────────────────────────────────────────
# /create_commercial
# ──────────────────────────────────────────────────────────────────────────────

@router.message(
    Command("create_commercial"),
    RoleFilter("sales", "manager", "owner"),
)
async def cmd_create_commercial(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    employee: Employee,
):
    await state.update_data(doc_type="commercial")
    await _ask_client(message, state, session, employee.id)


@router.message(
    Command("create_invoice"),
    RoleFilter("sales", "manager", "owner"),
)
async def cmd_create_invoice(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    employee: Employee,
):
    await state.update_data(doc_type="invoice")
    await _ask_client(message, state, session, employee.id)


async def _ask_client(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    employee_id: int,
):
    result = await session.execute(
        select(Client).where(Client.created_by == employee_id).limit(20)
    )
    clients = result.scalars().all()

    if not clients:
        await message.answer(
            "⚠️ У вас нет клиентов. Сначала добавьте клиента командой /new_client."
        )
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"👤 {c.name} ({c.phone or 'нет тел.'})",
            callback_data=f"doc_client_{c.id}",
        )]
        for c in clients
    ])

    await state.set_state(CreateDocFSM.waiting_client)
    await message.answer("👤 Выберите клиента:", reply_markup=kb)


# ── Выбор клиента ─────────────────────────────────────────────────────────────

@router.callback_query(CreateDocFSM.waiting_client, F.data.startswith("doc_client_"))
async def cb_doc_client(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
):
    client_id = int(callback.data.split("_")[-1])
    result = await session.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if not client:
        await callback.answer("Клиент не найден", show_alert=True)
        return

    await state.update_data(client_id=client_id, client_name=client.name, client_phone=client.phone or "")

    # Выбор услуги
    svc_result = await session.execute(select(Service).where(Service.is_active == True).limit(15))
    services = svc_result.scalars().all()

    if not services:
        await callback.message.answer("⚠️ Нет доступных услуг. Обратитесь к владельцу.")
        await state.clear()
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"🔧 {s.name} — {s.price:,.0f} ₸",
            callback_data=f"doc_service_{s.id}",
        )]
        for s in services
    ])
    await state.set_state(CreateDocFSM.waiting_service)
    await callback.message.edit_text("🔧 Выберите услугу:", reply_markup=kb)
    await callback.answer()


# ── Выбор услуги ─────────────────────────────────────────────────────────────

@router.callback_query(CreateDocFSM.waiting_service, F.data.startswith("doc_service_"))
async def cb_doc_service(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
):
    service_id = int(callback.data.split("_")[-1])
    result = await session.execute(select(Service).where(Service.id == service_id))
    svc = result.scalar_one_or_none()
    if not svc:
        await callback.answer("Услуга не найдена", show_alert=True)
        return

    await state.update_data(
        service_id=service_id,
        service_name=svc.name,
        service_description=svc.description or "",
        amount=float(svc.price),
    )
    await state.set_state(CreateDocFSM.waiting_amount)
    await callback.message.edit_text(
        f"💰 Сумма по умолчанию: <b>{svc.price:,.0f} ₸</b>\n"
        "Введите другую сумму или нажмите «Оставить»:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"✅ Оставить {svc.price:,.0f} ₸", callback_data="doc_keep_amount")]
        ]),
    )
    await callback.answer()


@router.callback_query(CreateDocFSM.waiting_amount, F.data == "doc_keep_amount")
async def cb_doc_keep_amount(callback: CallbackQuery, state: FSMContext):
    await _confirm_doc(callback.message, state, edit=True)
    await callback.answer()


@router.message(CreateDocFSM.waiting_amount)
async def msg_doc_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace(" ", "").replace(",", ".").replace("₸", ""))
        assert amount > 0
    except (ValueError, AssertionError):
        await message.answer("⚠️ Введите корректную сумму (только число).")
        return
    await state.update_data(amount=amount)
    await _confirm_doc(message, state, edit=False)


async def _confirm_doc(message: Message, state: FSMContext, edit: bool = False):
    data = await state.get_data()
    doc_type_name = "Коммерческое предложение" if data["doc_type"] == "commercial" else "Счёт на оплату"

    text = (
        f"📋 <b>Подтвердите создание документа:</b>\n\n"
        f"📄 Тип: {doc_type_name}\n"
        f"👤 Клиент: {data['client_name']}\n"
        f"🔧 Услуга: {data['service_name']}\n"
        f"💰 Сумма: {data['amount']:,.0f} ₸"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Создать", callback_data="doc_confirm"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="doc_cancel"),
        ]
    ])
    await state.set_state(CreateDocFSM.waiting_confirm)
    if edit:
        await message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await message.answer(text, reply_markup=kb, parse_mode="HTML")


# ── Финальное создание ────────────────────────────────────────────────────────

@router.callback_query(CreateDocFSM.waiting_confirm, F.data == "doc_confirm")
async def cb_doc_confirm(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    doc_service: DocumentService,
    employee: Employee,
):
    data = await state.get_data()
    await callback.message.edit_text("⏳ Генерирую документ...")

    # Создаём сделку если нет
    deal = Deal(
        client_id=data["client_id"],
        employee_id=employee.id,
        service_id=data["service_id"],
        amount=data["amount"],
        status=DealStatus.new,
    )
    session.add(deal)
    await session.flush()  # Получаем deal.id

    # Генерируем документ
    if data["doc_type"] == "commercial":
        url = await doc_service.create_commercial(
            client_name=data["client_name"],
            client_phone=data["client_phone"],
            service_name=data["service_name"],
            service_description=data["service_description"],
            amount=data["amount"],
            manager_name=employee.fio,
            deal_id=deal.id,
        )
        doc_type = DocType.commercial
    else:
        url = await doc_service.create_invoice(
            client_name=data["client_name"],
            service_name=data["service_name"],
            amount=data["amount"],
            deal_id=deal.id,
        )
        doc_type = DocType.invoice

    # Сохраняем документ в БД
    doc = Document(
        deal_id=deal.id,
        type=doc_type,
        file_url=url,
        created_by=employee.id,
    )
    session.add(doc)
    await session.commit()

    await callback.message.edit_text(
        f"✅ <b>Документ создан!</b>\n\n"
        f"📎 <a href='{url}'>Скачать документ</a>",
        parse_mode="HTML",
        disable_web_page_preview=False,
    )
    await state.clear()
    await callback.answer()


@router.callback_query(CreateDocFSM.waiting_confirm, F.data == "doc_cancel")
async def cb_doc_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Создание документа отменено.")
    await callback.answer()
