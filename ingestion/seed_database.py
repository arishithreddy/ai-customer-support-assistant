import csv

import json

from datetime import date, datetime, timezone

from decimal import Decimal, ROUND_HALF_UP

from pathlib import Path

from typing import Any, Optional

from uuid import uuid4


from sqlalchemy import func, select

from sqlalchemy.orm import Session


from backend.database.models import (

    AppUser,

    AuditLog,

    Base,

    Customer,

    Order,

    Product,

    Refund,

    SupportTicket,

)

from backend.database.session import DATABASE_FILE, SessionLocal, engine


PROJECT_ROOT = Path(__file__).resolve().parents[1]

MOCK_DATA_DIR = PROJECT_ROOT / "data" / "mock_business"


def read_csv(file_name: str) -> list[dict[str, str]]:

    file_path = MOCK_DATA_DIR / file_name

    if not file_path.exists():

        raise FileNotFoundError(f"Seed file not found: {file_path}")

    with file_path.open("r", encoding="utf-8-sig", newline="") as file:

        return list(csv.DictReader(file))


def optional_text(value: Optional[str]) -> Optional[str]:

    if value is None:

        return None

    cleaned = value.strip()

    return cleaned if cleaned else None


def parse_date(value: str) -> date:

    return date.fromisoformat(value.strip())


def parse_optional_date(value: Optional[str]) -> Optional[date]:

    cleaned = optional_text(value)

    return date.fromisoformat(cleaned) if cleaned else None


def parse_datetime(value: str) -> datetime:
    """

    CSV values contain dates. Store them as UTC timestamps at midnight.

    """

    parsed_date = date.fromisoformat(value.strip())

    return datetime(

        parsed_date.year,

        parsed_date.month,

        parsed_date.day,

        tzinfo=timezone.utc,

    )


def parse_bool(value: str) -> bool:

    normalized = value.strip().lower()

    if normalized not in {"true", "false"}:

        raise ValueError(f"Invalid boolean value: {value}")

    return normalized == "true"


def dollars_to_cents(value: str) -> int:

    amount = Decimal(value.strip()).quantize(

        Decimal("0.01"),

        rounding=ROUND_HALF_UP,

    )

    return int(amount * 100)


def seed_customers(session: Session) -> None:

    for row in read_csv("customers.csv"):

        session.add(

            Customer(

                customer_id=row["customer_id"],

                customer_name=row["customer_name"],

                customer_tier=row["customer_tier"],

                account_status=row["account_status"],

                country=row["country"],

                created_at=parse_date(row["created_at"]),

            )

        )


def seed_products(session: Session) -> None:

    for row in read_csv("products.csv"):

        session.add(

            Product(

                product_id=row["product_id"],

                product_name=row["product_name"],

                category=row["category"],

                warranty_months=int(row["warranty_months"]),

                returnable=parse_bool(row["returnable"]),

                is_digital=parse_bool(row["is_digital"]),

                price_cents=dollars_to_cents(row["price"]),

            )

        )


def seed_orders(session: Session) -> None:

    for row in read_csv("orders.csv"):

        session.add(

            Order(

                order_id=row["order_id"],

                customer_id=row["customer_id"],

                product_id=row["product_id"],

                order_status=row["order_status"],

                order_date=parse_date(row["order_date"]),

                ship_date=parse_optional_date(row["ship_date"]),

                delivery_date=parse_optional_date(row["delivery_date"]),

                shipping_method=row["shipping_method"],

                carrier=optional_text(row["carrier"]),

                tracking_status=row["tracking_status"],

                total_amount_cents=dollars_to_cents(row["total_amount"]),

            )

        )


def seed_refunds(session: Session) -> None:

    for row in read_csv("refunds.csv"):

        session.add(

            Refund(

                refund_id=row["refund_id"],

                order_id=row["order_id"],

                customer_id=row["customer_id"],

                refund_status=row["refund_status"],

                refund_reason=row["refund_reason"],

                requested_date=parse_date(row["requested_date"]),

                approved_date=parse_optional_date(row["approved_date"]),

                processed_date=parse_optional_date(row["processed_date"]),

                refund_amount_cents=dollars_to_cents(

                    row["refund_amount"]

                ),

            )

        )


def seed_tickets(session: Session) -> None:

    for row in read_csv("support_tickets.csv"):

        session.add(

            SupportTicket(

                ticket_id=row["ticket_id"],

                customer_id=row["customer_id"],

                order_id=optional_text(row["order_id"]),

                issue_type=row["issue_type"],

                priority=row["priority"],

                status=row["status"],

                created_at=parse_datetime(row["created_at"]),

                last_updated=parse_datetime(row["last_updated"]),

                summary=row["summary"],

            )

        )


def seed_app_users(session: Session) -> None:

    users = [

        AppUser(

            user_id="USR-CUST-001",

            username="customer_ava",

            identity_subject="local-customer-ava",

            role="customer",

            customer_id="CUST001",

            is_active=True,

        ),

        AppUser(

            user_id="USR-CUST-002",

            username="customer_liam",

            identity_subject="local-customer-liam",

            role="customer",

            customer_id="CUST002",

            is_active=True,

        ),

        AppUser(
            user_id="USR-CUST-005",

            username="customer_emma",

            identity_subject="local-customer-emma",

            role="customer",

            customer_id="CUST005",

            is_active=True,

        ),

        AppUser(

            user_id="USR-SUPPORT-001",

            username="support_agent_demo",

            identity_subject="local-support-agent-demo",

            role="support_agent",

            customer_id=None,

            is_active=True,

        ),

        AppUser(

            user_id="USR-SUPERVISOR-001",

            username="supervisor_demo",

            identity_subject="local-supervisor-demo",

            role="supervisor",

            customer_id=None,

            is_active=True,

        ),

        AppUser(

            user_id="USR-ADMIN-001",

            username="app_admin_demo",

            identity_subject="local-app-admin-demo",

            role="app_admin",

            customer_id=None,

            is_active=True,

        ),

    ]

    session.add_all(users)


def seed_initial_audit_event(session: Session) -> None:

    session.add(

        AuditLog(

            audit_id=f"AUD-{uuid4().hex}",

            actor_user_id="USR-ADMIN-001",

            action="seed_database",

            resource_type="database",

            resource_id="customer_support",

            outcome="allowed",

            reason_code="INITIAL_SYNTHETIC_DATA_LOAD",

            details_json=json.dumps(

                {

                    "data_classification": "synthetic",

                    "contains_real_customer_data": False,

                }

            ),

        )

    )


def count_rows(

    session: Session,

    model: type[Any],

) -> int:

    return int(

        session.scalar(

            select(func.count()).select_from(model)

        )

        or 0

    )


def print_summary(session: Session) -> None:

    models = [

        Customer,

        Product,

        Order,

        Refund,

        SupportTicket,

        AppUser,

        AuditLog,

    ]

    print("\nDatabase Seed Summary")

    print("-" * 70)

    for model in models:

        print(

            f"{model.__tablename__:<25}"

            f"{count_rows(session, model)}"

        )

    print(f"\nDatabase file: {DATABASE_FILE}")


def rebuild_database() -> None:
    """

    Rebuild the local development database from synthetic fixtures.



    Never use destructive rebuild logic against a production database.

    """

    engine.dispose()

    if DATABASE_FILE.exists():

        DATABASE_FILE.unlink()

    Base.metadata.create_all(bind=engine)

    with SessionLocal() as session:

        try:

            seed_customers(session)

            seed_products(session)

            session.flush()

            seed_orders(session)

            session.flush()

            seed_refunds(session)

            seed_tickets(session)

            seed_app_users(session)

            session.flush()

            seed_initial_audit_event(session)

            session.commit()

            print_summary(session)

        except Exception:

            session.rollback()

            raise


if __name__ == "__main__":

    rebuild_database()
