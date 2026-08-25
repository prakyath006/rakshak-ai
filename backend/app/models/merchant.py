"""Merchant model."""

from sqlalchemy import String, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Merchant(Base):
    __tablename__ = "merchants"

    merchant_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    industry: Mapped[str] = mapped_column(String(100), nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="INR")
    refund_policy: Mapped[str] = mapped_column(Text, nullable=True)
    cancellation_policy: Mapped[str] = mapped_column(Text, nullable=True)
    terms_url: Mapped[str] = mapped_column(String(500), nullable=True)
    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    payments: Mapped[list["Payment"]] = relationship(back_populates="merchant")
    orders: Mapped[list["Order"]] = relationship(back_populates="merchant")
    disputes: Mapped[list["Dispute"]] = relationship(back_populates="merchant")

    def __repr__(self) -> str:
        return f"<Merchant {self.merchant_id}: {self.name}>"
