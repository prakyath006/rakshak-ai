"""Payment model."""

from sqlalchemy import String, Numeric, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Payment(Base):
    __tablename__ = "payments"

    payment_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    merchant_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("merchants.merchant_id")
    )
    customer_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("customers.customer_id")
    )
    order_id: Mapped[str] = mapped_column(String(50), nullable=True)
    amount: Mapped[float] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(10), default="INR")
    payment_method: Mapped[str] = mapped_column(
        String(50)
    )  # card, upi, netbanking, wallet
    payment_status: Mapped[str] = mapped_column(
        String(50)
    )  # captured, failed, refunded
    card_network: Mapped[str] = mapped_column(
        String(50), nullable=True
    )  # visa, mastercard, rupay, amex
    payment_timestamp: Mapped[str] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    merchant: Mapped["Merchant"] = relationship(back_populates="payments")
    customer: Mapped["Customer"] = relationship(back_populates="payments")
    order: Mapped["Order"] = relationship(
        back_populates="payment", foreign_keys="Order.payment_id"
    )
    refunds: Mapped[list["Refund"]] = relationship(back_populates="payment")
    disputes: Mapped[list["Dispute"]] = relationship(back_populates="payment")

    def __repr__(self) -> str:
        return f"<Payment {self.payment_id}: ₹{self.amount}>"
