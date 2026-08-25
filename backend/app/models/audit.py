"""Audit log model."""

from sqlalchemy import String, DateTime, ForeignKey, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    audit_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    dispute_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("disputes.dispute_id")
    )
    stage: Mapped[str] = mapped_column(
        String(50)
    )  # INGESTED, CLASSIFIED, EVIDENCE_SEARCH, EVIDENCE_VERIFIED, DECISION_READY, HUMAN_REVIEW, PACKAGE_READY, SUBMITTED, OUTCOME
    action: Mapped[str] = mapped_column(String(200))
    input_data: Mapped[dict] = mapped_column(JSON, default=dict)
    output_data: Mapped[dict] = mapped_column(JSON, default=dict)
    decision_reason: Mapped[str] = mapped_column(String(500), nullable=True)
    timestamp: Mapped[str] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    dispute: Mapped["Dispute"] = relationship(back_populates="audit_logs")

    def __repr__(self) -> str:
        return f"<AuditLog {self.audit_id}: {self.stage} - {self.action}>"
