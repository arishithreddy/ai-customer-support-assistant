from sqlalchemy import func, select

from backend.database.models import AuditLog
from backend.database.session import SessionLocal
from backend.services.support_tool_service import SupportToolService


def get_audit_count() -> int:
    with SessionLocal() as session:
        return int(
            session.scalar(
                select(func.count()).select_from(AuditLog)
            )
            or 0
        )


def test_customer_own_order() -> None:
    # local-customer-ava -> CUST001 -> Arjun Mehta
    service = SupportToolService(
        identity_subject="local-customer-ava"
    )

    result = service.get_order_status("ORD001")

    assert result["status"] == "success"
    assert result["data"]["order_id"] == "ORD001"
    assert result["data"]["product_name"] == "Smartphone X1"

    # Customers should not receive internal fields.
    assert "customer_id" not in result["data"]
    assert "customer_name" not in result["data"]


def test_customer_cannot_access_another_order() -> None:
    # CUST001 trying to access CUST002's order
    service = SupportToolService(
        identity_subject="local-customer-ava"
    )

    result = service.get_order_status("ORD002")

    assert result["status"] == "denied"
    assert "data" not in result

    serialized = str(result)

    assert "CUST002" not in serialized
    assert "Sophia Williams" not in serialized
    assert "Wireless Headphones Pro" not in serialized


def test_customer_missing_and_unauthorized_are_indistinguishable() -> None:
    service = SupportToolService(
        identity_subject="local-customer-ava"
    )

    unauthorized = service.get_order_status("ORD002")
    missing = service.get_order_status("ORD999")

    assert unauthorized == missing


def test_support_agent_receives_masked_name() -> None:
    service = SupportToolService(
        identity_subject="local-support-agent-demo"
    )

    result = service.get_order_status("ORD002")

    assert result["status"] == "success"
    assert result["data"]["customer_id"] == "CUST002"

    # Support agents receive a masked customer name.
    assert result["data"]["customer_name"] != "Sophia Williams"
    assert "*" in result["data"]["customer_name"]

    # Support agents should not receive order amount.
    assert "total_amount" not in result["data"]


def test_supervisor_receives_authorized_fields() -> None:
    service = SupportToolService(
        identity_subject="local-supervisor-demo"
    )

    result = service.get_order_status("ORD002")

    assert result["status"] == "success"
    assert result["data"]["customer_name"] == "Sophia Williams"
    assert result["data"]["total_amount"] == "149.99"


def test_app_admin_cannot_access_customer_order() -> None:
    service = SupportToolService(
        identity_subject="local-app-admin-demo"
    )

    result = service.get_order_status("ORD001")

    assert result["status"] == "denied"
    assert "data" not in result


def test_customer_own_refund() -> None:
    # local-customer-liam -> CUST002 -> Sophia Williams
    #
    # REF010 -> ORD015 -> CUST002
    # REF010 status = completed
    service = SupportToolService(
        identity_subject="local-customer-liam"
    )

    result = service.get_refund_status("REF010")

    assert result["status"] == "success"
    assert result["data"]["refund_id"] == "REF010"
    assert result["data"]["order_id"] == "ORD015"
    assert result["data"]["refund_status"] == "completed"

    # Customers should not receive internal customer fields.
    assert "customer_id" not in result["data"]
    assert "customer_name" not in result["data"]


def test_customer_cannot_access_another_refund() -> None:
    # CUST002 trying to access REF005, which belongs to CUST001
    service = SupportToolService(
        identity_subject="local-customer-liam"
    )

    result = service.get_refund_status("REF005")

    assert result["status"] == "denied"
    assert "data" not in result


def test_customer_own_ticket() -> None:
    # local-customer-liam -> CUST002 -> TKT002
    service = SupportToolService(
        identity_subject="local-customer-liam"
    )

    result = service.get_ticket_status("TKT002")

    assert result["status"] == "success"
    assert result["data"]["ticket_id"] == "TKT002"

    # Customers should not receive customer_id.
    assert "customer_id" not in result["data"]


def test_product_data_is_available_to_authenticated_users() -> None:
    service = SupportToolService(
        identity_subject="local-customer-ava"
    )

    result = service.get_product_details("PROD001")

    assert result["status"] == "success"
    assert result["data"]["product_name"] == "Smartphone X1"


def test_unknown_identity_is_denied() -> None:
    service = SupportToolService(
        identity_subject="unknown-identity"
    )

    result = service.get_order_status("ORD001")

    assert result["status"] == "denied"
    assert "data" not in result


def main() -> None:
    initial_audit_count = get_audit_count()

    tests = [
        test_customer_own_order,
        test_customer_cannot_access_another_order,
        test_customer_missing_and_unauthorized_are_indistinguishable,
        test_support_agent_receives_masked_name,
        test_supervisor_receives_authorized_fields,
        test_app_admin_cannot_access_customer_order,
        test_customer_own_refund,
        test_customer_cannot_access_another_refund,
        test_customer_own_ticket,
        test_product_data_is_available_to_authenticated_users,
        test_unknown_identity_is_denied,
    ]

    for test in tests:
        test()
        print(f"{test.__name__}: passed")

    final_audit_count = get_audit_count()

    assert final_audit_count > initial_audit_count

    print(
        f"Audit records added: "
        f"{final_audit_count - initial_audit_count}"
    )

    print("All support tool security tests passed.")


if __name__ == "__main__":
    main()
