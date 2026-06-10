from datetime import datetime
from sqlalchemy import (
    BigInteger, String, DateTime, Integer, func,
)
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(64))
    language: Mapped[str] = mapped_column(String(5), default="en")
    phone: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Track(Base):
    __tablename__ = "tracks"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(512))
    artist: Mapped[str] = mapped_column(String(512))
    duration: Mapped[int | None] = mapped_column(Integer)
    youtube_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    file_path: Mapped[str] = mapped_column(String(1024))
    telegram_file_id: Mapped[str | None] = mapped_column(String(256))
    telegram_message_id: Mapped[int | None] = mapped_column(Integer)
    telegram_chat_id: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ChatLog(Base):
    __tablename__ = "chat_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    username: Mapped[str | None] = mapped_column(String(64))
    phone: Mapped[str | None] = mapped_column(String(32))
    message: Mapped[str] = mapped_column(String(4096))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
