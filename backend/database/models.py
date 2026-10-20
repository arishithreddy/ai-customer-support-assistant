from __future__ import annotations


from datetime import date, datetime, timezone

from typing import Optional


from sqlalchemy import (

    Boolean,

    CheckConstraint,

    Date,

    DateTime,

    ForeignKey,

    Index,

    Integer,

    String,

    Text,

)

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:

    return datetime.now(timezone.utc)


class Base(DeclarativeBase):

    pass


class Customer(Base):

    __tablename__ = "customers"

    customer_id: Mapped[str] = mapped_column(String(30), primary_key=True)

    customer_name: Mapped[str] = mapped_column(String(120), nullable=False)

    customer_tier: Mapped[str] = mapped_column(String(30), nullable=False)

    account_status: Mapped[str] = mapped_column(String(30), nullable=False)

    country: Mapped[str] = mapped_column(String(10), nullable=False)

    created_at: Mapped[date] = mapped_column(Date, nullable=False)

    orders: Mapped[list["Order"]] = relationship(back_populates="customer")

    refunds: Mapped[list["Refund"]] = relationship(back_populates="customer")

    tickets: Mapped[list["SupportTicket"]] = relationship(

        back_populates="customer"

    )

    users: Mapped[list["AppUser"]] = relationship(back_populates="customer")

    __table_args__ = (

        CheckConstraint(

            "customer_tier IN ('Standard', 'Premium', 'Enterprise')",

            name="ck_customers_tier",

        ),

        CheckConstraint(

            "account_status IN ('Active', 'Inactive', 'Suspended')",

            name="ck_customers_status",

        ),

    )


class Product(Base):

    __tablename__ = "products"

    product_id: Mapped[str] = mapped_column(String(30), primary_key=True)

    product_name: Mapped[str] = mapped_column(String(160), nullable=False)

    category: Mapped[str] = mapped_column(String(60), nullable=False)

    warranty_months: Mapped[int] = mapped_column(

        Integer,

        nullable=False,

        default=0,

    )

    returnable: Mapped[bool] = mapped_column(

        Boolean,

        nullable=False,

        default=True,

    )

    is_digital: Mapped[bool] = mapped_column(

        Boolean,

        nullable=False,

        default=False,

    )

    # Money is stored as cents instead of a floating-point number.

    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)

    orders: Mapped[list["Order"]] = relationship(back_populates="product")

    __table_args__ = (

        CheckConstraint(

            "warranty_months >= 0",

            name="ck_products_warranty_nonnegative",

        ),

        CheckConstraint(

            "price_cents >= 0",

            name="ck_products_price_nonnegative",

        ),

    )


class Order(Base):

    __tablename__ = "orders"

    order_id: Mapped[str] = mapped_column(String(30), primary_key=True)

    customer_id: Mapped[str] = mapped_column(

        ForeignKey("customers.customer_id"),

        nullable=False,

        index=True,

    )

    product_id: Mapped[str] = mapped_column(

        ForeignKey("products.product_id"),

        nullable=False,

        index=True,

    )

    order_status: Mapped[str] = mapped_column(String(30), nullable=False)

    order_date: Mapped[date] = mapped_column(Date, nullable=False)

    ship_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    delivery_date: Mapped[Optional[date]] = mapped_column(

        Date,

        nullable=True,

    )

    shipping_method: Mapped[str] = mapped_column(String(30), nullable=False)

    carrier: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    tracking_status: Mapped[str] = mapped_column(String(50), nullable=False)

    total_amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)

    customer: Mapped["Customer"] = relationship(back_populates="orders")

    product: Mapped["Product"] = relationship(back_populates="orders")

    refunds: Mapped[list["Refund"]] = relationship(back_populates="order")

    tickets: Mapped[list["SupportTicket"]] = relationship(

        back_populates="order"

    )

    __table_args__ = (

        CheckConstraint(

            "order_status IN "

            "('Processing', 'Shipped', 'Delivered', 'Cancelled', 'Refunded')",

            name="ck_orders_status",

        ),

        CheckConstraint(

            "total_amount_cents >= 0",

            name="ck_orders_amount_nonnegative",

        ),

        Index("ix_orders_customer_status", "customer_id", "order_status"),

    )


class Refund(Base):

    __tablename__ = "refunds"

    refund_id: Mapped[str] = mapped_column(String(30), primary_key=True)

    order_id: Mapped[str] = mapped_column(

        ForeignKey("orders.order_id"),

        nullable=False,

        index=True,

    )

    customer_id: Mapped[str] = mapped_column(

        ForeignKey("customers.customer_id"),

        nullable=False,

        index=True,

    )

    refund_status: Mapped[str] = mapped_column(String(30), nullable=False)

    refund_reason: Mapped[str] = mapped_column(String(100), nullable=False)

    requested_date: Mapped[date] = mapped_column(Date, nullable=False)

    approved_date: Mapped[Optional[date]] = mapped_column(

        Date,

        nullable=True,

    )

    processed_date: Mapped[Optional[date]] = mapped_column(

        Date,

        nullable=True,

    )

    refund_amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)

    order: Mapped["Order"] = relationship(back_populates="refunds")

    customer: Mapped["Customer"] = relationship(back_populates="refunds")

    __table_args__ = (

        CheckConstraint(

            "refund_status IN ('processing', 'approved', 'completed', 'denied')",

            name="ck_refunds_status",

        ),

        CheckConstraint(

            "refund_amount_cents >= 0",

            name="ck_refunds_amount_nonnegative",

        ),

    )


class SupportTicket(Base):

    __tablename__ = "support_tickets"

    ticket_id: Mapped[str] = mapped_column(String(30), primary_key=True)

    customer_id: Mapped[str] = mapped_column(

        ForeignKey("customers.customer_id"),

        nullable=False,

        index=True,

    )

    order_id: Mapped[Optional[str]] = mapped_column(

        ForeignKey("orders.order_id"),

        nullable=True,

        index=True,

    )

    issue_type: Mapped[str] = mapped_column(String(60), nullable=False)

    priority: Mapped[str] = mapped_column(String(20), nullable=False)

    status: Mapped[str] = mapped_column(String(30), nullable=False)

    created_at: Mapped[datetime] = mapped_column(

        DateTime(timezone=True),

        nullable=False,

    )

    last_updated: Mapped[datetime] = mapped_column(

        DateTime(timezone=True),

        nullable=False,

    )

    summary: Mapped[str] = mapped_column(Text, nullable=False)

    customer: Mapped["Customer"] = relationship(back_populates="tickets")

    order: Mapped[Optional["Order"]] = relationship(back_populates="tickets")

    __table_args__ = (

        CheckConstraint(

            "priority IN ('low', 'medium', 'high')",

            name="ck_tickets_priority",

        ),

        CheckConstraint(

            "status IN ('open', 'closed', 'escalated')",

            name="ck_tickets_status",

        ),

    )


class AppUser(Base):

    """

    Application identity mapped to a role.



    Authentication credentials are not stored here yet. In the authentication

    step, a verified JWT subject will map to identity_subject.



    A customer user must have a customer_id. Staff users should not.

    """

    __tablename__ = "app_users"

    user_id: Mapped[str] = mapped_column(String(40), primary_key=True)

    username: Mapped[str] = mapped_column(

        String(100),

        unique=True,

        nullable=False,

    )

    identity_subject: Mapped[str] = mapped_column(

        String(160),

        unique=True,

        nullable=False,

    )

    password_hash: Mapped[Optional[str]] = mapped_column(
        String(160),
        unique=True,
        nullable=True,
    )

    role: Mapped[str] = mapped_column(String(30), nullable=False)

    customer_id: Mapped[Optional[str]] = mapped_column(

        ForeignKey("customers.customer_id"),

        nullable=True,

        index=True,

    )

    is_active: Mapped[bool] = mapped_column(

        Boolean,

        nullable=False,

        default=True,

    )

    created_at: Mapped[datetime] = mapped_column(

        DateTime(timezone=True),

        nullable=False,

        default=utc_now,

    )

    customer: Mapped[Optional["Customer"]] = relationship(

        back_populates="users"

    )

    audit_events: Mapped[list["AuditLog"]] = relationship(

        back_populates="actor"

    )

    __table_args__ = (

        CheckConstraint(

            "role IN ('customer', 'support_agent', 'supervisor', 'app_admin')",

            name="ck_app_users_role",

        ),

        CheckConstraint(

            "(role = 'customer' AND customer_id IS NOT NULL) OR "

            "(role != 'customer' AND customer_id IS NULL)",

            name="ck_app_users_customer_mapping",

        ),

    )


class AuditLog(Base):

    """

    Security and tool-action audit trail.



    Request text and tool outputs should not be stored here by default because

    they may contain PII. Store concise metadata and redacted details.

    """

    __tablename__ = "audit_logs"

    audit_id: Mapped[str] = mapped_column(String(50), primary_key=True)

    actor_user_id: Mapped[Optional[str]] = mapped_column(

        ForeignKey("app_users.user_id"),

        nullable=True,

        index=True,

    )

    action: Mapped[str] = mapped_column(String(100), nullable=False)

    resource_type: Mapped[str] = mapped_column(String(60), nullable=False)

    resource_id: Mapped[Optional[str]] = mapped_column(

        String(100),

        nullable=True,

    )

    outcome: Mapped[str] = mapped_column(String(30), nullable=False)

    reason_code: Mapped[Optional[str]] = mapped_column(

        String(80),

        nullable=True,

    )

    # Must contain only redacted/non-sensitive JSON metadata.

    details_json: Mapped[str] = mapped_column(

        Text,

        nullable=False,

        default="{}",

    )

    created_at: Mapped[datetime] = mapped_column(

        DateTime(timezone=True),

        nullable=False,

        default=utc_now,

        index=True,

    )

    actor: Mapped[Optional["AppUser"]] = relationship(

        back_populates="audit_events"

    )

    __table_args__ = (

        CheckConstraint(

            "outcome IN ('allowed', 'denied', 'error')",

            name="ck_audit_logs_outcome",

        ),

        Index(

            "ix_audit_resource",

            "resource_type",

            "resource_id",

        ),
    )
