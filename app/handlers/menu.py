"""
app/handlers/menu.py

Обрабатывает нажатия кнопок главного меню.
Каждая кнопка вызывает нужный сервис или переходит в FSM.
"""
from __future__ import annotations

from datetime import date

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.keyboards.menus import get_menu_by_role
from app.models.db import Employee, RoleName, Deal, Shift, Client
from app.utils.states import (
    AddPositionFSM, CreateDocFSM, AddClientFSM, AddDealFSM, SetSalaryFSM
)

router = Router(name="menu")


# ──────────────────────────────────────────────────────────────────────────────
# /start для активных сотрудников — показывает меню
# ──────────────────────────────────────────────────────────────────────────────

async def show_main_menu(message: Message, employee: Employee):
    role_label = {
        RoleName.owner:    "👑 Владелец",
        RoleName.manager_: "🔧 Управляющий",
        RoleName.sales:    "💼 Менеджер",
    }.get(employee.role, "Сотрудник")

    await message.answer(
        f"👋 Добро пожаловать, <b>{employee.fio}</b>!\n"
        f"Роль: {role_label}\n\n"
        f"Выберите действие в меню ниже 👇",
        reply_markup=get_menu_by_role(employee.role),
        parse_mode="HTML",
    )


# ──────────────────────────────────────────────────────────────────────────────
# 👤 МОЙ КАБИНЕТ
# ──────────────────────────────────────────────────────────────────────────────

@router.message(F.text == "👤 Мой кабинет")
async def btn_cabinet(
    message: Message,
    session: AsyncSession,
    employee: Employee,
):
    today = date.today()

    # Статус смены
    shift_res = await session.execute(
        select(Shift).where(Shift.employee_id == employee.id, Shift.date == today)
    )
    shift = shift_res.scalar_one_or_none()
    on_shift = shift.is_on_shift if shift else False
    shift_icon = "🟢 На смене" if on_shift else "🔴 Не на смене"

    # Статистика сделок
    deals_text = ""
    if employee.role == RoleName.sales:
        total = await session.scalar(
            select(func.count(Deal.id)).where(Deal.employee_id == employee.id)
        )
        won = await session.scalar(
            select(func.count(Deal.id)).where(
                Deal.employee_id == employee.id, Deal.status == "won"
            )
        )
        total_sum = await session.scalar(
            select(func.sum(Deal.amount)).where(Deal.employee_id == employee.id)
        ) or 0
        deals_text = (
            f"\n\n📊 <b>Статистика:</b>\n"
            f"├ Всего сделок: {total}\n"
            f"├ Выиграно: {won}\n"
            f"└ Сумма: {total_sum:,.0f} ₸"
        )

    salary_text = ""
    if employee.salary and employee.role != RoleName.manager_:
        salary_text = f"\n💰 <b>Зарплата:</b> {employee.salary:,.0f} ₸"

    role_map = {
        RoleName.owner:    "👑 Владелец",
        RoleName.manager_: "🔧 Управляющий",
        RoleName.sales:    "💼 Менеджер по продажам",
    }

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📄 Мои документы", callback_data="my_docs")],
    ])

    await message.answer(
        f"👤 <b>Личный кабинет</b>\n\n"
        f"ФИО: <b>{employee.fio}</b>\n"
        f"Должность: {employee.position or '—'}\n"
        f"Роль: {role_map.get(employee.role, '—')}\n"
        f"Смена: {shift_icon}"
        f"{salary_text}"
        f"{deals_text}",
        reply_markup=kb,
        parse_mode="HTML",
    )


# ──────────────────────────────────────────────────────────────────────────────
# 🟢 НА СМЕНУ / УЙТИ СО СМЕНЫ
# ──────────────────────────────────────────────────────────────────────────────

@router.message(F.text == "🟢 На смену / Уйти со смены")
async def btn_shift_toggle(
    message: Message,
    session: AsyncSession,
    employee: Employee,
):
    today = date.today()
    result = await session.execute(
        select(Shift).where(Shift.employee_id == employee.id, Shift.date == today)
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

    if new_status:
        await message.answer("🟢 Вы вышли на смену! Удачного рабочего дня 💪")
    else:
        await message.answer("🔴 Вы ушли со смены. Хорошего отдыха!")


# ──────────────────────────────────────────────────────────────────────────────
# 👥 МОИ КЛИЕНТЫ
# ──────────────────────────────────────────────────────────────────────────────

@router.message(F.text == "👥 Мои клиенты")
async def btn_my_clients(
    message: Message,
    session: AsyncSession,
    employee: Employee,
):
    result = await session.execute(
        select(Client)
        .where(Client.created_by == employee.id)
        .order_by(Client.created_at.desc())
        .limit(20)
    )
    clients = result.scalars().all()

    if not clients:
        await message.answer(
            "📭 У вас пока нет клиентов.\n"
            "Нажмите <b>➕ Новый клиент</b> чтобы добавить.",
            parse_mode="HTML",
        )
        return

    lines = ["👥 <b>Мои клиенты:</b>\n"]
    for i, c in enumerate(clients, 1):
        lines.append(
            f"{i}. <b>{c.name}</b>\n"
            f"   📞 {c.phone or '—'}  🏙 {c.city or '—'}\n"
            f"   Источник: {c.source or '—'}"
        )

    await message.answer("\n".join(lines), parse_mode="HTML")


# ──────────────────────────────────────────────────────────────────────────────
# ➕ НОВЫЙ КЛИЕНТ
# ──────────────────────────────────────────────────────────────────────────────

@router.message(F.text == "➕ Новый клиент")
async def btn_new_client(message: Message, state: FSMContext):
    await state.set_state(AddClientFSM.waiting_name)
    await message.answer("👤 Введите <b>имя клиента</b>:", parse_mode="HTML")


@router.message(AddClientFSM.waiting_name)
async def fsm_client_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await state.set_state(AddClientFSM.waiting_phone)
    await message.answer("📞 Введите <b>телефон</b> клиента:", parse_mode="HTML")


@router.message(AddClientFSM.waiting_phone)
async def fsm_client_phone(message: Message, state: FSMContext):
    await state.update_data(phone=message.text.strip())
    await state.set_state(AddClientFSM.waiting_city)
    await message.answer("🏙 Введите <b>город</b> клиента:", parse_mode="HTML")


@router.message(AddClientFSM.waiting_city)
async def fsm_client_city(message: Message, state: FSMContext):
    await state.update_data(city=message.text.strip())
    await state.set_state(AddClientFSM.waiting_source)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Instagram", callback_data="src_instagram"),
            InlineKeyboardButton(text="Referral",  callback_data="src_referral"),
        ],
        [
            InlineKeyboardButton(text="WhatsApp",  callback_data="src_whatsapp"),
            InlineKeyboardButton(text="Другое",    callback_data="src_other"),
        ],
    ])
    await message.answer("📣 Выберите <b>источник</b> клиента:", reply_markup=kb, parse_mode="HTML")


from aiogram import F as AF
from aiogram.types import CallbackQuery


@router.callback_query(AddClientFSM.waiting_source, AF.data.startswith("src_"))
async def fsm_client_source(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    employee: Employee,
):
    source_map = {
        "src_instagram": "Instagram",
        "src_referral":  "Referral",
        "src_whatsapp":  "WhatsApp",
        "src_other":     "Другое",
    }
    source = source_map.get(callback.data, "Другое")
    data = await state.get_data()

    client = Client(
        name=data["name"],
        phone=data.get("phone"),
        city=data.get("city"),
        source=source,
        created_by=employee.id,
    )
    session.add(client)
    await session.commit()

    await callback.message.edit_text(
        f"✅ <b>Клиент добавлен!</b>\n\n"
        f"👤 {data['name']}\n"
        f"📞 {data.get('phone', '—')}\n"
        f"🏙 {data.get('city', '—')}\n"
        f"📣 Источник: {source}",
        parse_mode="HTML",
    )
    await state.clear()
    await callback.answer()


# ──────────────────────────────────────────────────────────────────────────────
# 📨 СОЗДАТЬ КП  /  🧾 СОЗДАТЬ СЧЁТ
# ──────────────────────────────────────────────────────────────────────────────

@router.message(F.text == "📨 Создать КП")
async def btn_create_commercial(message: Message, state: FSMContext, session: AsyncSession, employee: Employee):
    await state.update_data(doc_type="commercial")
    await _start_doc_flow(message, state, session, employee.id)


@router.message(F.text == "🧾 Создать счёт")
async def btn_create_invoice(message: Message, state: FSMContext, session: AsyncSession, employee: Employee):
    await state.update_data(doc_type="invoice")
    await _start_doc_flow(message, state, session, employee.id)


@router.message(F.text == "📄 Документы")
async def btn_docs(message: Message, state: FSMContext, session: AsyncSession, employee: Employee):
    """Для владельца/управляющего — выбор типа документа."""
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📨 КП", callback_data="doctype_commercial"),
            InlineKeyboardButton(text="🧾 Счёт", callback_data="doctype_invoice"),
        ],
        [
            InlineKeyboardButton(text="📑 Договор", callback_data="doctype_contract"),
            InlineKeyboardButton(text="📋 Акт", callback_data="doctype_act"),
        ],
    ])
    await message.answer("📄 Какой документ создать?", reply_markup=kb)


async def _start_doc_flow(message: Message, state: FSMContext, session: AsyncSession, emp_id: int):
    from app.models.db import Client
    result = await session.execute(
        select(Client).where(Client.created_by == emp_id).limit(20)
    )
    clients = result.scalars().all()

    if not clients:
        await message.answer(
            "⚠️ Нет клиентов. Сначала добавьте клиента через <b>➕ Новый клиент</b>.",
            parse_mode="HTML",
        )
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"👤 {c.name}",
            callback_data=f"doc_client_{c.id}",
        )]
        for c in clients
    ])
    await state.set_state(CreateDocFSM.waiting_client)
    await message.answer("👤 Выберите клиента:", reply_markup=kb)


# ──────────────────────────────────────────────────────────────────────────────
# 👥 ВСЕ СОТРУДНИКИ (владелец / управляющий)
# ──────────────────────────────────────────────────────────────────────────────

@router.message(F.text == "👥 Все сотрудники")
async def btn_all_employees(
    message: Message,
    session: AsyncSession,
    employee: Employee,
):
    if employee.role not in (RoleName.owner, RoleName.manager_):
        await message.answer("🚫 Нет доступа.")
        return

    result = await session.execute(
        select(Employee).where(Employee.is_active == True).order_by(Employee.fio)
    )
    employees = result.scalars().all()

    if not employees:
        await message.answer("📭 Нет активных сотрудников.")
        return

    role_map = {
        RoleName.owner:    "👑",
        RoleName.manager_: "🔧",
        RoleName.sales:    "💼",
    }

    # Смены сегодня
    today = date.today()
    shifts_res = await session.execute(
        select(Shift).where(Shift.date == today, Shift.is_on_shift == True)
    )
    on_shift_ids = {s.employee_id for s in shifts_res.scalars().all()}

    lines = [f"👥 <b>Все сотрудники ({len(employees)}):</b>\n"]
    for emp in employees:
        shift_dot = "🟢" if emp.id in on_shift_ids else "🔴"
        salary_part = f" | 💰 {emp.salary:,.0f} ₸" if emp.salary and employee.role == RoleName.owner else ""
        lines.append(
            f"{role_map.get(emp.role, '👤')} <b>{emp.fio}</b> {shift_dot}\n"
            f"   {emp.position or '—'}{salary_part}"
        )

    await message.answer("\n".join(lines), parse_mode="HTML")


# ──────────────────────────────────────────────────────────────────────────────
# 📊 ОТЧЁТЫ
# ──────────────────────────────────────────────────────────────────────────────

@router.message(F.text == "📊 Отчёты")
async def btn_reports(
    message: Message,
    session: AsyncSession,
    employee: Employee,
):
    if employee.role not in (RoleName.owner, RoleName.manager_):
        await message.answer("🚫 Нет доступа.")
        return

    # Общая статистика
    total_deals = await session.scalar(select(func.count(Deal.id))) or 0
    won_deals   = await session.scalar(
        select(func.count(Deal.id)).where(Deal.status == "won")
    ) or 0
    total_sum   = await session.scalar(select(func.sum(Deal.amount))) or 0
    total_clients = await session.scalar(select(func.count(Client.id))) or 0

    # Топ менеджеров
    from sqlalchemy import desc
    top_res = await session.execute(
        select(Employee.fio, func.count(Deal.id).label("cnt"), func.sum(Deal.amount).label("sm"))
        .join(Deal, Deal.employee_id == Employee.id)
        .group_by(Employee.id)
        .order_by(desc("sm"))
        .limit(5)
    )
    top = top_res.all()

    top_text = ""
    if top:
        top_text = "\n\n🏆 <b>Топ менеджеров:</b>\n"
        for i, (fio, cnt, sm) in enumerate(top, 1):
            top_text += f"{i}. {fio} — {cnt} сд. / {(sm or 0):,.0f} ₸\n"

    # Прибыль — только для владельца
    profit_text = ""
    if employee.role == RoleName.owner:
        profit_text = f"\n💵 <b>Выручка:</b> {total_sum:,.0f} ₸"

    await message.answer(
        f"📊 <b>Отчёт по агентству</b>\n\n"
        f"📋 Всего сделок: {total_deals}\n"
        f"✅ Выиграно: {won_deals}\n"
        f"👥 Клиентов: {total_clients}"
        f"{profit_text}"
        f"{top_text}",
        parse_mode="HTML",
    )


# ──────────────────────────────────────────────────────────────────────────────
# ➕ ДОБАВИТЬ ДОЛЖНОСТЬ (только владелец)
# ──────────────────────────────────────────────────────────────────────────────

@router.message(F.text == "➕ Добавить должность")
async def btn_add_position(
    message: Message,
    state: FSMContext,
    employee: Employee,
):
    if employee.role != RoleName.owner:
        await message.answer("🚫 Только владелец может добавлять должности.")
        return
    await state.set_state(AddPositionFSM.waiting_position_name)
    await message.answer(
        "📋 Введите <b>название должности</b>:\n"
        "<i>Например: Старший менеджер по продажам</i>",
        parse_mode="HTML",
    )


# ──────────────────────────────────────────────────────────────────────────────
# 💰 ЗАРПЛАТЫ (только владелец)
# ──────────────────────────────────────────────────────────────────────────────

@router.message(F.text == "💰 Зарплаты")
async def btn_salaries(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    employee: Employee,
):
    if employee.role != RoleName.owner:
        await message.answer("🚫 Только владелец видит зарплаты.")
        return

    result = await session.execute(
        select(Employee).where(Employee.is_active == True).order_by(Employee.fio)
    )
    employees = result.scalars().all()

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"👤 {e.fio} — {e.salary:,.0f} ₸" if e.salary else f"👤 {e.fio} — не задана",
            callback_data=f"set_salary_{e.id}",
        )]
        for e in employees
    ])

    await state.set_state(SetSalaryFSM.waiting_employee)
    await message.answer(
        "💰 <b>Управление зарплатами</b>\n\nВыберите сотрудника для изменения:",
        reply_markup=kb,
        parse_mode="HTML",
    )


@router.callback_query(SetSalaryFSM.waiting_employee, AF.data.startswith("set_salary_"))
async def cb_set_salary_employee(callback: CallbackQuery, state: FSMContext):
    emp_id = int(callback.data.split("_")[-1])
    await state.update_data(target_employee_id=emp_id)
    await state.set_state(SetSalaryFSM.waiting_amount)
    await callback.message.edit_text(
        "💰 Введите <b>новую зарплату</b> (только цифры, в тенге):",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(SetSalaryFSM.waiting_amount)
async def fsm_set_salary_amount(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
):
    try:
        amount = float(message.text.replace(" ", "").replace(",", ""))
        assert amount > 0
    except (ValueError, AssertionError):
        await message.answer("⚠️ Введите корректную сумму (только число).")
        return

    data = await state.get_data()
    result = await session.execute(
        select(Employee).where(Employee.id == data["target_employee_id"])
    )
    emp = result.scalar_one_or_none()
    if emp:
        emp.salary = amount
        await session.commit()
        await message.answer(
            f"✅ Зарплата <b>{emp.fio}</b> установлена: <b>{amount:,.0f} ₸</b>",
            parse_mode="HTML",
        )
    await state.clear()


# ──────────────────────────────────────────────────────────────────────────────
# 💼 НОВАЯ СДЕЛКА
# ──────────────────────────────────────────────────────────────────────────────

@router.message(F.text == "💼 Новая сделка")
async def btn_new_deal(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    employee: Employee,
):
    result = await session.execute(
        select(Client).where(Client.created_by == employee.id).limit(20)
    )
    clients = result.scalars().all()

    if not clients:
        await message.answer(
            "⚠️ Нет клиентов. Добавьте клиента через <b>➕ Новый клиент</b>.",
            parse_mode="HTML",
        )
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"👤 {c.name}", callback_data=f"deal_client_{c.id}")]
        for c in clients
    ])
    await state.set_state(AddDealFSM.waiting_client)
    await message.answer("💼 Выберите клиента для сделки:", reply_markup=kb)


@router.callback_query(AddDealFSM.waiting_client, AF.data.startswith("deal_client_"))
async def cb_deal_client(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    from app.models.db import Service
    client_id = int(callback.data.split("_")[-1])
    await state.update_data(client_id=client_id)

    svc_res = await session.execute(select(Service).where(Service.is_active == True).limit(15))
    services = svc_res.scalars().all()

    if not services:
        await callback.message.edit_text("⚠️ Нет доступных услуг.")
        await state.clear()
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🔧 {s.name} — {s.price:,.0f} ₸", callback_data=f"deal_service_{s.id}")]
        for s in services
    ])
    await state.set_state(AddDealFSM.waiting_service)
    await callback.message.edit_text("🔧 Выберите услугу:", reply_markup=kb)
    await callback.answer()


@router.callback_query(AddDealFSM.waiting_service, AF.data.startswith("deal_service_"))
async def cb_deal_service(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    from app.models.db import Service
    service_id = int(callback.data.split("_")[-1])
    svc = await session.get(Service, service_id)
    await state.update_data(service_id=service_id, amount=float(svc.price))
    await state.set_state(AddDealFSM.waiting_amount)
    await callback.message.edit_text(
        f"💰 Сумма по умолчанию: <b>{svc.price:,.0f} ₸</b>\n"
        "Введите свою сумму или нажмите «Оставить»:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"✅ Оставить {svc.price:,.0f} ₸", callback_data="deal_keep_amount")]
        ]),
    )
    await callback.answer()


@router.callback_query(AddDealFSM.waiting_amount, AF.data == "deal_keep_amount")
async def cb_deal_keep_amount(callback: CallbackQuery, state: FSMContext):
    await _ask_deal_status(callback.message, state, edit=True)
    await callback.answer()


@router.message(AddDealFSM.waiting_amount)
async def fsm_deal_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace(" ", "").replace(",", ""))
        assert amount > 0
    except (ValueError, AssertionError):
        await message.answer("⚠️ Введите корректную сумму.")
        return
    await state.update_data(amount=amount)
    await _ask_deal_status(message, state, edit=False)


async def _ask_deal_status(message: Message, state: FSMContext, edit: bool):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🆕 Новая",     callback_data="deal_status_new"),
            InlineKeyboardButton(text="🔄 В работе",  callback_data="deal_status_in_work"),
        ],
        [
            InlineKeyboardButton(text="✅ Выиграна",  callback_data="deal_status_won"),
            InlineKeyboardButton(text="❌ Проиграна", callback_data="deal_status_lost"),
        ],
    ])
    await state.set_state(AddDealFSM.waiting_status)
    if edit:
        await message.edit_text("📌 Выберите статус сделки:", reply_markup=kb)
    else:
        await message.answer("📌 Выберите статус сделки:", reply_markup=kb)


@router.callback_query(AddDealFSM.waiting_status, AF.data.startswith("deal_status_"))
async def cb_deal_status(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    employee: Employee,
):
    from app.models.db import Deal, DealStatus
    status_map = {
        "deal_status_new":     DealStatus.new,
        "deal_status_in_work": DealStatus.in_work,
        "deal_status_won":     DealStatus.won,
        "deal_status_lost":    DealStatus.lost,
    }
    status = status_map[callback.data]
    data = await state.get_data()

    deal = Deal(
        client_id=data["client_id"],
        employee_id=employee.id,
        service_id=data["service_id"],
        amount=data["amount"],
        status=status,
    )
    session.add(deal)
    await session.commit()

    status_labels = {
        DealStatus.new:     "🆕 Новая",
        DealStatus.in_work: "🔄 В работе",
        DealStatus.won:     "✅ Выиграна",
        DealStatus.lost:    "❌ Проиграна",
    }

    await callback.message.edit_text(
        f"✅ <b>Сделка создана!</b>\n\n"
        f"💰 Сумма: {data['amount']:,.0f} ₸\n"
        f"📌 Статус: {status_labels[status]}",
        parse_mode="HTML",
    )
    await state.clear()
    await callback.answer()
