"""Order model."""

from sqlalchemy import String, Integer, Numeric, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Order(Base):
    __tablename__ = "orders"

    order_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    merchant_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("merchants.merchant_id")
    )
    customer_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("customers.customer_id")
    )
    payment_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("payments.payment_id"), nullable=True
    )
    product_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("products.product_id")
    )
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    order_amount: Mapped[float] = mapped_column(Numeric(12, 2))
    order_status: Mapped[str] = mapped_column(
        String(50)
    )  # confirmed, shipped, delivered, cancelled, returned
    cancelled_at: Mapped[str] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    merchant: Mapped["Merchant"] = relationship(back_populates="orders")
    customer: Mapped["Customer"] = relationship(back_populates="orders")
    payment: Mapped["Payment"] = relationship(
        back_populates="order", foreign_keys=[payment_id]
    )
    product: Mapped["Product"] = relationship()
    shipments: Mapped[list["Shipment"]] = relationship(back_populates="order")
    communications: Mapped[list["Communication"]] = relationship(
        back_populates="order"
    )

    def __repr__(self) -> str:
        return f"<Order {self.order_id}: {self.order_status}>"
