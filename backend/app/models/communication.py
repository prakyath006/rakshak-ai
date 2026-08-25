"""Communication model."""

from sqlalchemy import String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Communication(Base):
    __tablename__ = "communications"

    communication_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    customer_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("customers.customer_id")
    )
    order_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("orders.order_id"), nullable=True
    )
    channel: Mapped[str] = mapped_column(String(50))  # email, phone, chat
    direction: Mapped[str] = mapped_column(
        String(20)
    )  # inbound (customer→merchant) or outbound (merchant→customer)
    subject: Mapped[str] = mapped_column(String(500), nullable=True)
    message: Mapped[str] = mapped_column(Text)
    timestamp: Mapped[str] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    customer: Mapped["Customer"] = relationship(back_populates="communications")
    order: Mapped["Order"] = relationship(back_populates="communications")

    def __repr__(self) -> str:
        return f"<Communication {self.communication_id}: {self.channel} {self.direction}>"
