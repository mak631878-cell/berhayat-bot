"""
app/utils/states.py — FSM-стейты для aiogram 3
"""
from aiogram.fsm.state import State, StatesGroup


class RegistrationFSM(StatesGroup):
    """Регистрация нового сотрудника по invite-ссылке."""
    waiting_fio        = State()
    waiting_birth_date = State()
    waiting_city       = State()
    waiting_phone      = State()
    waiting_education  = State()
    waiting_photo      = State()
    waiting_consent    = State()   # Кнопки «Согласие» + «Отправить»


class AddClientFSM(StatesGroup):
    """Добавление нового клиента менеджером."""
    waiting_name   = State()
    waiting_phone  = State()
    waiting_city   = State()
    waiting_source = State()


class AddDealFSM(StatesGroup):
    """Создание новой сделки."""
    waiting_client  = State()
    waiting_service = State()
    waiting_amount  = State()
    waiting_status  = State()
    waiting_notes   = State()


class CreateDocFSM(StatesGroup):
    """Генерация документа (КП / счёт / договор / акт)."""
    waiting_doc_type = State()
    waiting_client   = State()
    waiting_service  = State()
    waiting_amount   = State()
    waiting_confirm  = State()


class AddPositionFSM(StatesGroup):
    """Владелец создаёт должность + invite-токен."""
    waiting_position_name = State()


class SetSalaryFSM(StatesGroup):
    """Владелец устанавливает зарплату сотруднику."""
    waiting_employee = State()
    waiting_amount   = State()
