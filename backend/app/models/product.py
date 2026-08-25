"""Product model."""

from sqlalchemy import String, Text, Numeric, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Product(Base):
    __tablename__ = "products"

    product_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text, nullable=True)
    specification: Mapped[str] = mapped_column(Text, nullable=True)
    price: Mapped[float] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(10), default="INR")
    category: Mapped[str] = mapped_column(String(100), nullable=True)
    image_url: Mapped[str] = mapped_column(String(500), nullable=True)
    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<Product {self.product_id}: {self.name}>"
