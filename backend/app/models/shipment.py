"""Shipment model."""

from sqlalchemy import String, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Shipment(Base):
    __tablename__ = "shipments"

    shipment_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    order_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("orders.order_id")
    )
    carrier: Mapped[str] = mapped_column(String(100))
    tracking_number: Mapped[str] = mapped_column(String(200), nullable=True)
    shipped_at: Mapped[str] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[str] = mapped_column(DateTime(timezone=True), nullable=True)
    delivery_status: Mapped[str] = mapped_column(
        String(50)
    )  # pending, shipped, in_transit, delivered, lost, returned
    delivery_address_city: Mapped[str] = mapped_column(String(100), nullable=True)
    delivery_address_match: Mapped[bool] = mapped_column(
        default=True
    )  # does delivery address match billing?
    items_shipped: Mapped[int] = mapped_column(default=1)  # for partial delivery cases
    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    order: Mapped["Order"] = relationship(back_populates="shipments")

    def __repr__(self) -> str:
        return f"<Shipment {self.shipment_id}: {self.delivery_status}>"
