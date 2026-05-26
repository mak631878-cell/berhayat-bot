"""
app/handlers/registration.py

FSM-регистрация нового сотрудника:
  /start invite_<token>  →  запрашивает данные по шагам  →  отправляет на аккредитацию
"""
from __future__ import annotations

import logging
import re
from datetime import date, datetime

from aiogram import Router, F
from aiogram.filters import CommandStart, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import Employee
from app.services.invite import InviteService
from app.services.notify import NotifyService
from app.services.document import StorageService
from app.utils.states import RegistrationFSM
from app.keyboards.menus import get_menu_by_role

logger = logging.getLogger(__name__)
router = Router(name="registration")

PHONE_RE = re.compile(r"^\+?[78]\d{9,10}$")


# ──────────────────────────────────────────────────────────────────────────────
# /start — точка входа
# ──────────────────────────────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(
    message: Message,
    command: CommandObject,
    state: FSMContext,
    session: AsyncSession,
    invite_service: InviteService,
    employee: Employee | None,
):
    args = command.args or ""

    # Уже зарегистрированный активный сотрудник
    if employee and employee.is_active:
        role_label = {
            "owner":   "👑 Владелец",
            "manager": "🔧 Управляющий",
            "sales":   "💼 Менеджер",
        }.get(employee.role.value, "Сотрудник")
        await message.answer(
            f"👋 Добро пожаловать, <b>{employee.fio}</b>!\n"
            f"Роль: {role_label}\n\n"
            f"Выберите действие 👇",
            reply_markup=get_menu_by_role(employee.role),
            parse_mode="HTML",
        )
        return

    # Invite-ссылка
    if args.startswith("invite_"):
        token = args[len("invite_"):]
        payload = await invite_service.validate_token(token)

        if payload is None:
            await message.answer(
                "❌ Ссылка недействительна или устарела.\n"
                "Попросите владельца создать новую."
            )
            return

        await state.update_data(token=token, position=payload["position"])
        await state.set_state(RegistrationFSM.waiting_fio)
        await message.answer(
            f"🎉 Добро пожаловать в БЕРХАЯТ!\n"
            f"Должность: <b>{payload['position']}</b>\n\n"
            "Начнём регистрацию. Введите ваше <b>ФИО</b> полностью:",
            parse_mode="HTML",
        )
        return

    await message.answer(
        "👋 Привет! Для доступа к боту вам нужна ссылка-приглашение от владельца."
    )


# ──────────────────────────────────────────────────────────────────────────────
# Шаг 1: ФИО
# ──────────────────────────────────────────────────────────────────────────────

@router.message(RegistrationFSM.waiting_fio)
async def reg_fio(message: Message, state: FSMContext):
    fio = (message.text or "").strip()
    if len(fio) < 5:
        await message.answer("⚠️ Введите полное ФИО (минимум 5 символов).")
        return

    await state.update_data(fio=fio)
    await state.set_state(RegistrationFSM.waiting_birth_date)
    await message.answer(
        "📅 Введите дату рождения в формате <b>ДД.ММ.ГГГГ</b>:",
        parse_mode="HTML",
    )


# ──────────────────────────────────────────────────────────────────────────────
# Шаг 2: Дата рождения
# ──────────────────────────────────────────────────────────────────────────────

@router.message(RegistrationFSM.waiting_birth_date)
async def reg_birth_date(message: Message, state: FSMContext):
    raw = (message.text or "").strip()
    try:
        dt = datetime.strptime(raw, "%d.%m.%Y").date()
    except ValueError:
        await message.answer("⚠️ Неверный формат. Введите дату как <b>01.01.1990</b>.", parse_mode="HTML")
        return

    today = date.today()
    age = today.year - dt.year - ((today.month, today.day) < (dt.month, dt.day))
    if age < 16 or age > 80:
        await message.answer("⚠️ Укажите корректный возраст (16–80 лет).")
        return

    await state.update_data(birth_date=dt.isoformat())
    await state.set_state(RegistrationFSM.waiting_city)
    await message.answer("🏙 Введите ваш <b>город проживания</b>:", parse_mode="HTML")


# ──────────────────────────────────────────────────────────────────────────────
# Шаг 3: Город
# ──────────────────────────────────────────────────────────────────────────────

@router.message(RegistrationFSM.waiting_city)
async def reg_city(message: Message, state: FSMContext):
    city = (message.text or "").strip()
    if not city:
        await message.answer("⚠️ Введите название города.")
        return

    await state.update_data(city=city)
    await state.set_state(RegistrationFSM.waiting_phone)

    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Поделиться номером", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
    await message.answer(
        "📞 Введите <b>номер телефона</b> или нажмите кнопку ниже:",
        reply_markup=kb,
        parse_mode="HTML",
    )


# ──────────────────────────────────────────────────────────────────────────────
# Шаг 4: Телефон
# ──────────────────────────────────────────────────────────────────────────────

@router.message(RegistrationFSM.waiting_phone, F.contact)
async def reg_phone_contact(message: Message, state: FSMContext):
    phone = message.contact.phone_number
    await state.update_data(phone=phone)
    await _ask_education(message, state)


@router.message(RegistrationFSM.waiting_phone, F.text)
async def reg_phone_text(message: Message, state: FSMContext):
    phone = (message.text or "").strip().replace(" ", "").replace("-", "")
    if not PHONE_RE.match(phone):
        await message.answer("⚠️ Укажите корректный номер, например: <b>+79001234567</b>", parse_mode="HTML")
        return
    await state.update_data(phone=phone)
    await _ask_education(message, state)


async def _ask_education(message: Message, state: FSMContext):
    await state.set_state(RegistrationFSM.waiting_education)
    await message.answer(
        "🎓 Укажите <b>сведения об образовании</b> (учебное заведение, специальность, год):",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="HTML",
    )


# ──────────────────────────────────────────────────────────────────────────────
# Шаг 5: Образование
# ──────────────────────────────────────────────────────────────────────────────

@router.message(RegistrationFSM.waiting_education)
async def reg_education(message: Message, state: FSMContext):
    edu = (message.text or "").strip()
    if len(edu) < 10:
        await message.answer("⚠️ Пожалуйста, опишите образование подробнее.")
        return

    await state.update_data(education=edu)
    await state.set_state(RegistrationFSM.waiting_photo)
    await message.answer(
        "📸 Загрузите <b>фотографию</b> (JPG/PNG, до 5 МБ):\n"
        "<i>Используйте фото, а не документ</i>",
        parse_mode="HTML",
    )


# ──────────────────────────────────────────────────────────────────────────────
# Шаг 6: Фотография
# ──────────────────────────────────────────────────────────────────────────────

@router.message(RegistrationFSM.waiting_photo, F.photo)
async def reg_photo(
    message: Message,
    state: FSMContext,
    storage: StorageService,
):
    photo = message.photo[-1]  # Наибольшее разрешение

    # Проверка размера (~5 МБ)
    if photo.file_size and photo.file_size > 5 * 1024 * 1024:
        await message.answer("⚠️ Фото слишком большое. Максимум 5 МБ.")
        return

    # Загружаем в S3
    file_info = await message.bot.get_file(photo.file_id)
    downloaded = await message.bot.download_file(file_info.file_path)
    photo_url = await storage.upload_bytes(
        data=downloaded.read(),
        filename=f"employees/{message.from_user.id}_photo.jpg",
        content_type="image/jpeg",
    )

    await state.update_data(photo_url=photo_url)
    await state.set_state(RegistrationFSM.waiting_consent)

    # Кнопки согласия
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="✅ Даю согласие на обработку персональных данных",
            callback_data="consent_agree"
        )],
        [InlineKeyboardButton(
            text="📤 ОТПРАВИТЬ НА АККРЕДИТАЦИЮ",
            callback_data="submit_registration"
        )],
    ])

    data = await state.get_data()
    await message.answer(
        f"📋 <b>Проверьте данные перед отправкой:</b>\n\n"
        f"👤 ФИО: {data['fio']}\n"
        f"📅 Дата рождения: {data['birth_date']}\n"
        f"🏙 Город: {data['city']}\n"
        f"📞 Телефон: {data['phone']}\n"
        f"🎓 Образование: {data['education'][:100]}...\n"
        f"📸 Фото: загружено\n\n"
        f"⚠️ Сначала нажмите «Согласие», затем «Отправить».",
        reply_markup=kb,
        parse_mode="HTML",
    )


@router.message(RegistrationFSM.waiting_photo)
async def reg_photo_wrong(message: Message):
    await message.answer("⚠️ Пожалуйста, отправьте фото (не документ, не текст).")


# ──────────────────────────────────────────────────────────────────────────────
# Шаг 7: Согласие
# ──────────────────────────────────────────────────────────────────────────────

@router.callback_query(RegistrationFSM.waiting_consent, F.data == "consent_agree")
async def reg_consent(callback: CallbackQuery, state: FSMContext):
    await state.update_data(consent=True)
    await callback.answer("✅ Согласие принято!")
    await callback.message.edit_text(
        callback.message.text + "\n\n✅ <b>Согласие на обработку ПД получено.</b>\n"
        "Нажмите «ОТПРАВИТЬ НА АККРЕДИТАЦИЮ».",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="📤 ОТПРАВИТЬ НА АККРЕДИТАЦИЮ",
                callback_data="submit_registration"
            )],
        ]),
        parse_mode="HTML",
    )


# ──────────────────────────────────────────────────────────────────────────────
# Шаг 8: Финальная отправка
# ──────────────────────────────────────────────────────────────────────────────

@router.callback_query(RegistrationFSM.waiting_consent, F.data == "submit_registration")
async def reg_submit(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    invite_service: InviteService,
    notify_service: NotifyService,
):
    data = await state.get_data()

    if not data.get("consent"):
        await callback.answer(
            "⚠️ Сначала дайте согласие на обработку персональных данных!",
            show_alert=True,
        )
        return

    token = data["token"]
    birth_date = date.fromisoformat(data["birth_date"])

    emp = await invite_service.finalize_registration(
        db=session,
        token=token,
        telegram_id=callback.from_user.id,
        fio=data["fio"],
        birth_date=birth_date,
        city=data["city"],
        phone=data["phone"],
        education=data["education"],
        photo_url=data["photo_url"],
    )

    if emp is None:
        await callback.answer("❌ Ошибка. Токен устарел.", show_alert=True)
        await state.clear()
        return

    # Удаляем токен из Redis (одноразовый)
    await invite_service.consume_token(token)

    # Уведомляем владельца
    await notify_service.send_accreditation_request(emp)

    await callback.message.edit_text(
        "✅ <b>Заявка на аккредитацию отправлена!</b>\n\n"
        "Владелец рассмотрит её и уведомит вас о результате.",
        parse_mode="HTML",
    )
    await state.clear()
