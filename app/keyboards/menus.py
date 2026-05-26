"""
app/keyboards/menus.py — главные меню для каждой роли
"""
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


# ──────────────────────────────────────────────────────────────────────────────
# ВЛАДЕЛЕЦ — полное меню
# ──────────────────────────────────────────────────────────────────────────────

def owner_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="👤 Мой кабинет"),
                KeyboardButton(text="👥 Все сотрудники"),
            ],
            [
                KeyboardButton(text="💼 Новая сделка"),
                KeyboardButton(text="👥 Мои клиенты"),
            ],
            [
                KeyboardButton(text="📄 Документы"),
                KeyboardButton(text="📊 Отчёты"),
            ],
            [
                KeyboardButton(text="➕ Добавить должность"),
                KeyboardButton(text="💰 Зарплаты"),
            ],
            [
                KeyboardButton(text="🟢 На смену / Уйти со смены"),
            ],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие...",
    )


# ──────────────────────────────────────────────────────────────────────────────
# УПРАВЛЯЮЩИЙ — без зарплат и добавления должностей
# ──────────────────────────────────────────────────────────────────────────────

def manager_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="👤 Мой кабинет"),
                KeyboardButton(text="👥 Все сотрудники"),
            ],
            [
                KeyboardButton(text="💼 Новая сделка"),
                KeyboardButton(text="👥 Мои клиенты"),
            ],
            [
                KeyboardButton(text="📄 Документы"),
                KeyboardButton(text="📊 Отчёты"),
            ],
            [
                KeyboardButton(text="🟢 На смену / Уйти со смены"),
            ],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие...",
    )


# ──────────────────────────────────────────────────────────────────────────────
# МЕНЕДЖЕР ПО ПРОДАЖАМ
# ──────────────────────────────────────────────────────────────────────────────

def sales_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="👤 Мой кабинет"),
                KeyboardButton(text="👥 Мои клиенты"),
            ],
            [
                KeyboardButton(text="💼 Новая сделка"),
                KeyboardButton(text="➕ Новый клиент"),
            ],
            [
                KeyboardButton(text="📨 Создать КП"),
                KeyboardButton(text="🧾 Создать счёт"),
            ],
            [
                KeyboardButton(text="🟢 На смену / Уйти со смены"),
            ],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие...",
    )


# ──────────────────────────────────────────────────────────────────────────────
# Получить меню по роли
# ──────────────────────────────────────────────────────────────────────────────

from app.models.db import RoleName


def get_menu_by_role(role: RoleName) -> ReplyKeyboardMarkup:
    if role == RoleName.owner:
        return owner_menu()
    elif role == RoleName.manager_:
        return manager_menu()
    else:
        return sales_menu()
