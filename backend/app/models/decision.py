"""Decision model."""

from sqlalchemy import String, Float, Text, DateTime, ForeignKey, Integer, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Decision(Base):
    __tablename__ = "decisions"

    decision_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    dispute_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("disputes.dispute_id")
    )
    recommendation: Mapped[str] = mapped_column(
        String(50)
    )  # CONTEST, REVIEW, DO_NOT_CONTEST
    confidence: Mapped[float] = mapped_column(Float)
    evidence_completeness: Mapped[float] = mapped_column(Float)
    evidence_consistency: Mapped[float] = mapped_column(Float, default=1.0)
    contradiction_count: Mapped[int] = mapped_column(Integer, default=0)
    evidence_strength: Mapped[str] = mapped_column(
        String(50)
    )  # HIGH, MEDIUM, LOW
    reasoning: Mapped[str] = mapped_column(Text)
    missing_critical: Mapped[list] = mapped_column(JSON, default=list)
    missing_optional: Mapped[list] = mapped_column(JSON, default=list)
    contradictions: Mapped[list] = mapped_column(JSON, default=list)
    
    # Rebuttal output from LLM
    rebuttal_text: Mapped[str] = mapped_column(Text, nullable=True)
    citations: Mapped[list] = mapped_column(JSON, default=list)
    unsupported_claims: Mapped[list] = mapped_column(JSON, default=list)
    
    # Human approval gate
    human_status: Mapped[str] = mapped_column(
        String(50), default="PENDING"
    )  # PENDING, APPROVED, REJECTED, MODIFIED
    reviewed_by: Mapped[str] = mapped_column(String(100), nullable=True)
    reviewed_at: Mapped[str] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    dispute: Mapped["Dispute"] = relationship(back_populates="decisions")

    def __repr__(self) -> str:
        return f"<Decision {self.decision_id}: {self.recommendation} ({self.evidence_strength})>"
