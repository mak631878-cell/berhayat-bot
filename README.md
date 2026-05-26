# 🤖 Telegram-бот БЕРХАЯТ — Внутренний корпоративный бот

## Стек технологий
- **Python 3.11+** + **aiogram 3.x**
- **PostgreSQL 16** + **SQLAlchemy 2.0 async** + **asyncpg**
- **Redis 7** — FSM-состояния и кэш
- **Alembic** — миграции БД
- **ReportLab / python-docx** — генерация PDF и DOCX
- **aioboto3** — загрузка файлов в S3 / Yandex Cloud
- **Docker Compose** — деплой

## Структура проекта

```
berhayat_bot/
├── app/
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── start.py          # /start, приглашения, онбординг
│   │   ├── registration.py   # FSM-регистрация нового сотрудника
│   │   ├── cabinet.py        # /my_cabinet — личный кабинет
│   │   ├── clients.py        # /new_client, /my_clients
│   │   ├── deals.py          # /new_deal, список сделок
│   │   ├── documents.py      # /create_commercial, /create_invoice
│   │   ├── employees.py      # /all_employees, /set_salary
│   │   ├── reports.py        # /reports — сводки
│   │   └── shifts.py         # /shift_on, /shift_off
│   ├── middlewares/
│   │   ├── __init__.py
│   │   └── role_access.py    # Проверка ролей + логирование
│   ├── models/
│   │   ├── __init__.py
│   │   └── db.py             # SQLAlchemy ORM-модели
│   ├── services/
│   │   ├── __init__.py
│   │   ├── invite.py         # Генерация и проверка invite_token
│   │   ├── deal.py           # Логика сделок
│   │   ├── document.py       # Генерация PDF/DOCX + загрузка в S3
│   │   └── notify.py         # Уведомления владельцу
│   ├── keyboards/
│   │   ├── __init__.py
│   │   └── inline.py         # InlineKeyboardMarkup фабрики
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── states.py         # FSM-стейты
│   │   └── validators.py     # Валидация дат, телефонов, фото
│   └── templates/
│       ├── commercial.html   # Шаблон КП (HTML → PDF)
│       └── invoice.html      # Шаблон счёта (HTML → PDF)
├── migrations/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 001_initial.py    # Начальная схема БД
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── .env.example
├── alembic.ini
├── main.py                   # Точка входа
└── requirements.txt
```

## Быстрый старт

### Локально
```bash
cp .env.example .env
# Заполнить .env своими значениями

pip install -r requirements.txt
alembic upgrade head
python main.py
```

### Docker
```bash
docker-compose -f docker/docker-compose.yml up -d --build
```
