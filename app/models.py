from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def now() -> datetime:
    return datetime.now(UTC)


class Credential(Base):
    __tablename__ = "credentials"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255))
    refresh_token: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Location(Base):
    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    account: Mapped[str] = mapped_column(String(100))
    title: Mapped[str] = mapped_column(String(255))
    address: Mapped[str] = mapped_column(String(500), default="")
    website: Mapped[str] = mapped_column(String(500), default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_post: Mapped[bool] = mapped_column(Boolean, default=True)
    backfill_done: Mapped[bool] = mapped_column(Boolean, default=False)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    business_context: Mapped[str] = mapped_column(Text, default="")
    city: Mapped[str] = mapped_column(String(255), default="")
    signature: Mapped[str] = mapped_column(String(255), default="")
    contact: Mapped[str] = mapped_column(String(255), default="")
    formal: Mapped[bool] = mapped_column(Boolean, default=True)
    default_language: Mapped[str] = mapped_column(String(10), default="fr")
    banned_phrases: Mapped[str] = mapped_column(Text, default="")

    reviews: Mapped[list["Review"]] = relationship(back_populates="location")


class ReviewStatus:
    NEW = "new"
    AWAITING_APPROVAL = "awaiting_approval"
    QUEUED = "queued"
    POSTED = "posted"
    SKIPPED = "skipped"
    FAILED = "failed"
    EXTERNAL = "external"


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (UniqueConstraint("location_id", "review_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"))
    review_id: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(500))
    reviewer: Mapped[str] = mapped_column(String(255), default="")
    stars: Mapped[int] = mapped_column(Integer, default=0)
    comment: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    status: Mapped[str] = mapped_column(String(30), default=ReviewStatus.NEW, index=True)
    backfill: Mapped[bool] = mapped_column(Boolean, default=False)
    language: Mapped[str] = mapped_column(String(10), default="")
    draft: Mapped[str] = mapped_column(Text, default="")
    risk_reason: Mapped[str] = mapped_column(Text, default="")
    notified: Mapped[bool] = mapped_column(Boolean, default=False)
    reply: Mapped[str] = mapped_column(Text, default="")
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str] = mapped_column(Text, default="")

    location: Mapped[Location] = relationship(back_populates="reviews")


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    review_id: Mapped[int | None] = mapped_column(ForeignKey("reviews.id"))
    action: Mapped[str] = mapped_column(String(50))
    detail: Mapped[str] = mapped_column(Text, default="")
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
