"""Dispute model."""

from sqlalchemy import String, Numeric, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Dispute(Base):
    __tablename__ = "disputes"

    dispute_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    payment_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("payments.payment_id")
    )
    merchant_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("merchants.merchant_id")
    )
    amount: Mapped[float] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(10), default="INR")
    amount_deducted: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0)
    reason_code: Mapped[str] = mapped_column(String(50))
    reason_description: Mapped[str] = mapped_column(String(500), nullable=True)
    phase: Mapped[str] = mapped_column(
        String(50), default="chargeback"
    )  # fraud, retrieval, chargeback, pre_arbitration, arbitration
    status: Mapped[str] = mapped_column(
        String(50), default="open"
    )  # open, under_review, won, lost, closed
    respond_by: Mapped[str] = mapped_column(DateTime(timezone=True))
    customer_claim_text: Mapped[str] = mapped_column(String(1000), nullable=True)
    
    # Synthetic/Ground Truth metadata (for evaluation only)
    ground_truth: Mapped[str] = mapped_column(
        String(50), nullable=True
    )  # contestable, non_contestable, ambiguous
    
    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    payment: Mapped["Payment"] = relationship(back_populates="disputes")
    merchant: Mapped["Merchant"] = relationship(back_populates="disputes")
    evidence_items: Mapped[list["Evidence"]] = relationship(back_populates="dispute")
    decisions: Mapped[list["Decision"]] = relationship(back_populates="dispute")
    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="dispute")

    def __repr__(self) -> str:
        return f"<Dispute {self.dispute_id}: {self.reason_code} - ₹{self.amount}>"
