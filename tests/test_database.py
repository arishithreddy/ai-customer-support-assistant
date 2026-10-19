from sqlalchemy import func, select

from sqlalchemy.exc import IntegrityError

 

from backend.database.models import (

    AppUser,

    AuditLog,

    Customer,

    Order,

    Product,

    Refund,

    SupportTicket,

)

from backend.database.repositories import (

    OrderRepository,

    RefundRepository,

    UserRepository,

)

from backend.database.session import DATABASE_FILE, SessionLocal

 

 

EXPECTED_COUNTS = {

    Customer: 10,

    Product: 10,

    Order: 15,

    Refund: 10,

    SupportTicket: 10,

    AppUser: 5,

    AuditLog: 1,

}

 

 

def get_count(session, model) -> int:

    return int(

        session.scalar(

            select(func.count()).select_from(model)

        )

        or 0

    )

 

 

def test_row_counts(session) -> None:

    for model, expected_count in EXPECTED_COUNTS.items():

        actual_count = get_count(session, model)

 

        assert actual_count == expected_count, (

            f"{model.__tablename__}: "

            f"expected {expected_count}, found {actual_count}"

        )

 

 

def test_order_relationships(session) -> None:

    order = OrderRepository.get_by_id(session, "ORD001")

    assert order is not None
    assert order.customer.customer_id == "CUST001"
    assert order.product.product_id == "PROD001"
    assert order.product.product_name == "Smartphone X1"

    result = OrderRepository.to_internal_dict(order)

    assert result["order_id"] == "ORD001"
    assert result["customer_id"] == "CUST001"
    assert result["total_amount"] == "699.99"

 

 

def test_refund_relationships(session) -> None:

    refund = RefundRepository.get_by_id(session, "REF001")

    assert refund is not None
    assert refund.order_id == "ORD004"
    assert refund.customer_id == "CUST004"

    order_refunds = RefundRepository.get_for_order(
        session,
        "ORD004",
    )

    assert len(order_refunds) == 1
    assert order_refunds[0].refund_id == "REF001"

 

 

def test_customer_identity_mapping(session) -> None:

    customer_user = UserRepository.get_by_user_id(
        session,
        "USR-CUST-001",
    )

    assert customer_user is not None
    assert customer_user.role == "customer"
    assert customer_user.customer_id == "CUST001"

    support_user = UserRepository.get_by_user_id(
        session,
        "USR-SUPPORT-001",
    )

    assert support_user is not None
    assert support_user.role == "support_agent"
    assert support_user.customer_id is None

 

 

def test_foreign_key_enforcement(session) -> None:

    existing_order = OrderRepository.get_by_id(
        session,
        "ORD001",
    )

    assert existing_order is not None

    invalid_order = Order(
        order_id="ORD-INVALID",
        customer_id="CUST-DOES-NOT-EXIST",
        product_id="PROD001",
        order_status="Processing",
        order_date=existing_order.order_date,
        ship_date=None,
        delivery_date=None,
        shipping_method="Standard",
        carrier=None,
        tracking_status="Processing",
        total_amount_cents=1000,
    )

    session.add(invalid_order)

    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        return

    raise AssertionError("SQLite foreign-key enforcement is disabled.")

 

 

def main() -> None:

    if not DATABASE_FILE.exists():

        raise FileNotFoundError(

            "Database not found. Run: python -m ingestion.seed_database"

        )

 

    with SessionLocal() as session:

        test_row_counts(session)

        print("Row count validation: passed")

 

        test_order_relationships(session)

        print("Order relationship validation: passed")

 

        test_refund_relationships(session)

        print("Refund relationship validation: passed")

 

        test_customer_identity_mapping(session)

        print("Identity and customer mapping validation: passed")

 

        test_foreign_key_enforcement(session)

        print("Foreign-key enforcement validation: passed")

 

    print("All database tests passed.")

 

 

if __name__ == "__main__":

    main()