"""SQLAlchemy models for Polydictions database."""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all models."""

    pass


class User(Base):
    """Telegram user who subscribed to the bot."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(Integer, unique=True, index=True, nullable=False)
    is_paused: Mapped[bool] = mapped_column(Boolean, default=False)
    news_interval: Mapped[int] = mapped_column(Integer, default=300)  # seconds
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    keywords: Mapped[list["Keyword"]] = relationship(
        "Keyword", back_populates="user", cascade="all, delete-orphan"
    )
    categories: Mapped[list["UserCategory"]] = relationship(
        "UserCategory", back_populates="user", cascade="all, delete-orphan"
    )
    alerts: Mapped[list["PriceAlert"]] = relationship(
        "PriceAlert", back_populates="user", cascade="all, delete-orphan"
    )
    watchlist: Mapped[list["WatchlistItem"]] = relationship(
        "WatchlistItem", back_populates="user", cascade="all, delete-orphan"
    )


class SeenEvent(Base):
    """Events that have been processed (for deduplication)."""

    __tablename__ = "seen_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Keyword(Base):
    """User's keyword filters."""

    __tablename__ = "keywords"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    keyword: Mapped[str] = mapped_column(String(100), nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="keywords")

    __table_args__ = (UniqueConstraint("user_id", "keyword", name="uq_user_keyword"),)


class UserCategory(Base):
    """User's category filters."""

    __tablename__ = "user_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="categories")

    __table_args__ = (UniqueConstraint("user_id", "category", name="uq_user_category"),)


class PriceAlert(Base):
    """Price alerts set by users."""

    __tablename__ = "price_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    event_slug: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    condition: Mapped[str] = mapped_column(String(2), nullable=False)  # ">" or "<"
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    outcome_index: Mapped[int] = mapped_column(Integer, default=0)
    is_triggered: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    triggered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="alerts")

    __table_args__ = (
        UniqueConstraint(
            "user_id", "event_slug", "condition", "threshold", "outcome_index", name="uq_alert"
        ),
    )


class WatchlistItem(Base):
    """User's watchlist items."""

    __tablename__ = "watchlist"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    event_slug: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship("User", back_populates="watchlist")

    __table_args__ = (UniqueConstraint("user_id", "event_slug", name="uq_user_watchlist"),)


class NewsCache(Base):
    """Cache for event context/news to detect changes."""

    __tablename__ = "news_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_slug: Mapped[str] = mapped_column(String(200), unique=True, index=True, nullable=False)
    context_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    context_preview: Mapped[str] = mapped_column(Text, nullable=True)  # First 500 chars
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class PostedEvent(Base):
    """Events posted to Telegram channel (for Chrome extension sync)."""

    __tablename__ = "posted_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[str] = mapped_column(String(100), nullable=False)
    event_slug: Mapped[str] = mapped_column(String(200), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=True)
    volume: Mapped[float] = mapped_column(Float, nullable=True)
    liquidity: Mapped[float] = mapped_column(Float, nullable=True)
    posted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
