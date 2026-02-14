from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16), default='user')
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class LoginAttempt(Base):
    __tablename__ = 'login_attempts'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), index=True)
    ip_address: Mapped[str] = mapped_column(String(64), index=True)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    lock_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_attempt: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
