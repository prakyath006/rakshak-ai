"""Refund model."""

from sqlalchemy import String, Numeric, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Refund(Base):
    __tablename__ = "refunds"

    refund_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    payment_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("payments.payment_id")
    )
    amount: Mapped[float] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(10), default="INR")
    reason: Mapped[str] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(
        String(50)
    )  # pending, processed, failed
    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    payment: Mapped["Payment"] = relationship(back_populates="refunds")

    def __repr__(self) -> str:
        return f"<Refund {self.refund_id}: ₹{self.amount} ({self.status})>"
