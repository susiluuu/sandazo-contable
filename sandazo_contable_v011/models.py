from datetime import datetime, timezone
from sqlalchemy import String, Integer, Boolean, ForeignKey, DateTime, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base

def now(): return datetime.now(timezone.utc)

class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(160))
    password_hash: Mapped[str] = mapped_column(String(255))
    is_superadmin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

class Company(Base):
    __tablename__ = 'companies'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    rfc: Mapped[str] = mapped_column(String(13), unique=True, index=True)
    regime: Mapped[str] = mapped_column(String(120), default='')
    fiscal_year: Mapped[int] = mapped_column(Integer, default=2026)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class Membership(Base):
    __tablename__ = 'memberships'
    __table_args__ = (UniqueConstraint('user_id','company_id'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    company_id: Mapped[int] = mapped_column(ForeignKey('companies.id'))
    role: Mapped[str] = mapped_column(String(20))

class Account(Base):
    __tablename__ = 'accounts'
    __table_args__ = (UniqueConstraint('company_id', 'code'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey('companies.id'), index=True)
    code: Mapped[str] = mapped_column(String(35))
    name: Mapped[str] = mapped_column(String(200))
    nature: Mapped[str] = mapped_column(String(12))
    parent_id: Mapped[int | None] = mapped_column(ForeignKey('accounts.id'), nullable=True)
    sat_group: Mapped[str] = mapped_column(String(25), default='')
    active: Mapped[bool] = mapped_column(Boolean, default=True)

class Audit(Base):
    __tablename__ = 'audit'
    id: Mapped[int] = mapped_column(primary_key=True)
    actor_user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    company_id: Mapped[int | None] = mapped_column(ForeignKey('companies.id'), nullable=True)
    action: Mapped[str] = mapped_column(String(50))
    detail: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class CompanySettings(Base):
    __tablename__ = 'company_settings'
    company_id: Mapped[int] = mapped_column(ForeignKey('companies.id'), primary_key=True)
    base_currency: Mapped[str] = mapped_column(String(3), default='MXN')
    allow_usd: Mapped[bool] = mapped_column(Boolean, default=True)
    client_email: Mapped[str] = mapped_column(String(255), default='')
    client_phone: Mapped[str] = mapped_column(String(24), default='')
    opinions_day: Mapped[int] = mapped_column(Integer, default=1)
    sat_opinion: Mapped[bool] = mapped_column(Boolean, default=True)
    imss_opinion: Mapped[bool] = mapped_column(Boolean, default=True)
    infonavit_opinion: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_send_opinions: Mapped[bool] = mapped_column(Boolean, default=True)
    reminders_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    reminders_days: Mapped[str] = mapped_column(String(40), default='5,3,1,0')
    reminder_whatsapp: Mapped[bool] = mapped_column(Boolean, default=True)
    reminder_email: Mapped[bool] = mapped_column(Boolean, default=True)
    logo_file: Mapped[str] = mapped_column(String(90), default='')

class Obligation(Base):
    __tablename__ = 'obligations'
    __table_args__ = (UniqueConstraint('company_id','tax_type','period_year','period_month','version'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey('companies.id'), index=True)
    tax_type: Mapped[str] = mapped_column(String(90))
    period_year: Mapped[int] = mapped_column(Integer)
    period_month: Mapped[int] = mapped_column(Integer)
    version: Mapped[int] = mapped_column(Integer, default=1)
    amount_cents: Mapped[int] = mapped_column(Integer, default=0)
    due_date: Mapped[str] = mapped_column(String(10))
    payment_reference: Mapped[str] = mapped_column(String(100), default='')
    status: Mapped[str] = mapped_column(String(24), default='pendiente_presentacion')
    submitted_at: Mapped[str] = mapped_column(String(10), default='')
    paid_at: Mapped[str] = mapped_column(String(10), default='')
    notes: Mapped[str] = mapped_column(String(400), default='')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class ReminderEvent(Base):
    __tablename__ = 'reminder_events'
    id: Mapped[int] = mapped_column(primary_key=True)
    obligation_id: Mapped[int] = mapped_column(ForeignKey('obligations.id'), index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey('companies.id'), index=True)
    channel: Mapped[str] = mapped_column(String(20))
    intended_at: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(30), default='pendiente_integracion')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
