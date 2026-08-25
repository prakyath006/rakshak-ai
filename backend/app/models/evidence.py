"""Evidence model."""

from sqlalchemy import String, Float, Text, DateTime, ForeignKey, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Evidence(Base):
    __tablename__ = "evidence"

    evidence_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    dispute_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("disputes.dispute_id")
    )
    type: Mapped[str] = mapped_column(
        String(100)
    )  # DELIVERY_CONFIRMATION, INVOICE, CUSTOMER_COMMUNICATION, etc.
    razorpay_field: Mapped[str] = mapped_column(
        String(100), nullable=True
    )  # shipping_proof, billing_proof, customer_communication, etc.
    source: Mapped[str] = mapped_column(String(100))  # logistics_db, orders_db, etc.
    source_record_id: Mapped[str] = mapped_column(String(100), nullable=True)
    reliability: Mapped[float] = mapped_column(Float, default=1.0)
    verification_status: Mapped[str] = mapped_column(
        String(50), default="VERIFIED"
    )  # VERIFIED, UNVERIFIED, CONTRADICTED
    content: Mapped[dict] = mapped_column(JSON, default=dict)
    file_path: Mapped[str] = mapped_column(String(500), nullable=True)
    content_hash: Mapped[str] = mapped_column(String(100), nullable=True)
    timestamp: Mapped[str] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    dispute: Mapped["Dispute"] = relationship(back_populates="evidence_items")

    def __repr__(self) -> str:
        return f"<Evidence {self.evidence_id}: {self.type} ({self.verification_status})>"
