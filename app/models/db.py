"""
app/models/db.py — ORM-модели (SQLAlchemy 2.0 async)
"""
from __future__ import annotations

import enum
from datetime import datetime, date
from typing import Optional, List

from sqlalchemy import (
    BigInteger, String, Text, Boolean, Date, DateTime,
    Numeric, ForeignKey, Enum as SAEnum, func
)
from sqlalchemy.orm import (
    DeclarativeBase, Mapped, mapped_column,
    relationship, AsyncAttrs
)


class Base(DeclarativeBase):
    pass


# ─────────────────────────── Роли ───────────────────────────

class RoleName(str, enum.Enum):
    owner      = "owner"       # Владелец
    manager_   = "manager"     # Управляющий
    sales      = "sales"       # Менеджер по продажам


# ─────────────────────────── Сотрудники ─────────────────────

class Employee(Base):
    __tablename__ = "employees"

    id:           Mapped[int]            = mapped_column(primary_key=True)
    telegram_id:  Mapped[int]            = mapped_column(BigInteger, unique=True, nullable=True)
    fio:          Mapped[str]            = mapped_column(String(255))
    birth_date:   Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    city:         Mapped[Optional[str]]  = mapped_column(String(100), nullable=True)
    phone:        Mapped[Optional[str]]  = mapped_column(String(30), nullable=True)
    education:    Mapped[Optional[str]]  = mapped_column(Text, nullable=True)
    photo_url:    Mapped[Optional[str]]  = mapped_column(String(512), nullable=True)
    role:         Mapped[RoleName]       = mapped_column(SAEnum(RoleName), default=RoleName.sales)
    position:     Mapped[Optional[str]]  = mapped_column(String(200), nullable=True)  # Должность из invite
    salary:       Mapped[Optional[float]]= mapped_column(Numeric(12, 2), nullable=True)
    is_active:    Mapped[bool]           = mapped_column(Boolean, default=False)
    invite_token: Mapped[Optional[str]]  = mapped_column(String(64), unique=True, nullable=True)
    invited_by:   Mapped[Optional[int]]  = mapped_column(ForeignKey("employees.id"), nullable=True)
    consent_pd:   Mapped[bool]           = mapped_column(Boolean, default=False)
    created_at:   Mapped[datetime]       = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Связи
    clients:   Mapped[List["Client"]]  = relationship(back_populates="creator")
    deals:     Mapped[List["Deal"]]    = relationship(back_populates="employee")
    shifts:    Mapped[List["Shift"]]   = relationship(back_populates="employee")


# ─────────────────────────── Клиенты ────────────────────────

class Client(Base):
    __tablename__ = "clients"

    id:         Mapped[int]           = mapped_column(primary_key=True)
    name:       Mapped[str]           = mapped_column(String(255))
    phone:      Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    city:       Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    source:     Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_by: Mapped[int]           = mapped_column(ForeignKey("employees.id"))
    created_at: Mapped[datetime]      = mapped_column(DateTime(timezone=True), server_default=func.now())

    creator: Mapped["Employee"]  = relationship(back_populates="clients")
    deals:   Mapped[List["Deal"]] = relationship(back_populates="client")


# ─────────────────────────── Услуги ─────────────────────────

class Service(Base):
    __tablename__ = "services"

    id:          Mapped[int]           = mapped_column(primary_key=True)
    name:        Mapped[str]           = mapped_column(String(255))
    price:       Mapped[float]         = mapped_column(Numeric(12, 2))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active:   Mapped[bool]          = mapped_column(Boolean, default=True)

    deals: Mapped[List["Deal"]] = relationship(back_populates="service")


# ─────────────────────────── Сделки ─────────────────────────

class DealStatus(str, enum.Enum):
    new        = "new"
    in_work    = "in_work"
    won        = "won"
    lost       = "lost"


class Deal(Base):
    __tablename__ = "deals"

    id:          Mapped[int]             = mapped_column(primary_key=True)
    client_id:   Mapped[int]             = mapped_column(ForeignKey("clients.id"))
    employee_id: Mapped[int]             = mapped_column(ForeignKey("employees.id"))
    service_id:  Mapped[Optional[int]]   = mapped_column(ForeignKey("services.id"), nullable=True)
    amount:      Mapped[float]           = mapped_column(Numeric(14, 2))
    status:      Mapped[DealStatus]      = mapped_column(SAEnum(DealStatus), default=DealStatus.new)
    notes:       Mapped[Optional[str]]   = mapped_column(Text, nullable=True)
    created_at:  Mapped[datetime]        = mapped_column(DateTime(timezone=True), server_default=func.now())

    client:    Mapped["Client"]           = relationship(back_populates="deals")
    employee:  Mapped["Employee"]         = relationship(back_populates="deals")
    service:   Mapped[Optional["Service"]]= relationship(back_populates="deals")
    documents: Mapped[List["Document"]]   = relationship(back_populates="deal")


# ─────────────────────────── Документы ──────────────────────

class DocType(str, enum.Enum):
    contract   = "contract"    # Договор
    act        = "act"         # Акт
    commercial = "commercial"  # КП
    invoice    = "invoice"     # Счёт


class Document(Base):
    __tablename__ = "documents"

    id:         Mapped[int]     = mapped_column(primary_key=True)
    deal_id:    Mapped[int]     = mapped_column(ForeignKey("deals.id"))
    type:       Mapped[DocType] = mapped_column(SAEnum(DocType))
    file_url:   Mapped[str]     = mapped_column(String(512))
    created_by: Mapped[int]     = mapped_column(ForeignKey("employees.id"))
    created_at: Mapped[datetime]= mapped_column(DateTime(timezone=True), server_default=func.now())

    deal: Mapped["Deal"] = relationship(back_populates="documents")


# ─────────────────────────── Смены ──────────────────────────

class Shift(Base):
    __tablename__ = "shifts"

    id:          Mapped[int]  = mapped_column(primary_key=True)
    employee_id: Mapped[int]  = mapped_column(ForeignKey("employees.id"))
    date:        Mapped[date] = mapped_column(Date, default=date.today)
    is_on_shift: Mapped[bool] = mapped_column(Boolean, default=True)

    employee: Mapped["Employee"] = relationship(back_populates="shifts")


# ─────────────────────────── Логи ───────────────────────────

class Log(Base):
    __tablename__ = "logs"

    id:          Mapped[int]           = mapped_column(primary_key=True)
    employee_id: Mapped[Optional[int]] = mapped_column(ForeignKey("employees.id"), nullable=True)
    action:      Mapped[str]           = mapped_column(String(200))
    details:     Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at:  Mapped[datetime]      = mapped_column(DateTime(timezone=True), server_default=func.now())
