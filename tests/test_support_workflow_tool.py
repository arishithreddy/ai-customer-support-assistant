from sqlalchemy import func, select

 

from backend.database.models import SupportTicket

from backend.database.session import SessionLocal

from backend.services.support_tool_service import SupportToolService

 

 

def get_ticket_count() -> int:

    with SessionLocal() as session:

        return int(

            session.scalar(

                select(func.count()).select_from(SupportTicket)

            )

            or 0

        )

 

 

def test_classify_refund_escalation_request() -> None:

    service = SupportToolService(

        identity_subject="local-customer-emma"

    )

 

    result = service.classify_support_request(

        "This is the third time I contacted support and nobody helped my refund issue."

    )

 

    assert result["status"] == "success"

    assert result["data"]["issue_type"] == "refund"

    assert result["data"]["priority"] == "high"

    assert result["data"]["sentiment"] == "frustrated"

 

 

def test_decide_escalation() -> None:

    service = SupportToolService(

        identity_subject="local-customer-emma"

    )

 

    result = service.decide_escalation(

        message="This is the third time nobody helped my refund issue.",

        issue_type="refund",

        priority="high",

        sentiment="frustrated",

    )

 

    assert result["status"] == "success"

    assert result["data"]["should_escalate"] is True

    assert result["data"]["recommended_status"] == "escalated"

 

 

def test_customer_creates_ticket_for_own_order() -> None:

    initial_count = get_ticket_count()

 

    service = SupportToolService(

        identity_subject="local-customer-emma"

    )

 

    result = service.create_support_ticket(

        summary="Coffee maker arrived damaged and I need help with the refund.",

        issue_type="damaged_item",

        priority="medium",

        order_id="ORD005",

        escalate=False,

    )

 

    assert result["status"] == "success"

    assert result["data"]["ticket_id"].startswith("TICK")

    assert result["data"]["order_id"] == "ORD005"

    assert result["data"]["status"] == "open"

    assert "customer_id" not in result["data"]

 

    final_count = get_ticket_count()

    assert final_count == initial_count + 1

 

 

def test_customer_cannot_create_ticket_for_other_customer_order() -> None:

    service = SupportToolService(

        identity_subject="local-customer-ava"

    )

 

    result = service.create_support_ticket(

        summary="I need help with this order.",

        issue_type="order_status",

        priority="low",

        order_id="ORD002",

        escalate=False,

    )

 

    assert result["status"] == "denied"

    assert "data" not in result

 

 

def test_support_agent_creates_escalated_ticket_for_customer() -> None:

    initial_count = get_ticket_count()

 

    service = SupportToolService(

        identity_subject="local-support-agent-demo"

    )

 

    result = service.create_support_ticket(

        summary="Tracking has not updated for over a week and needs carrier investigation.",

        issue_type="lost_package",

        priority="high",

        order_id="ORD008",

        customer_id="CUST008",

        escalate=True,

    )

 

    assert result["status"] == "success"

    assert result["data"]["status"] == "escalated"

    assert result["data"]["priority"] == "high"

    assert result["data"]["customer_id"] == "CUST008"

 

    final_count = get_ticket_count()

    assert final_count == initial_count + 1

 

 

def test_app_admin_cannot_create_ticket() -> None:

    service = SupportToolService(

        identity_subject="local-app-admin-demo"

    )

 

    result = service.create_support_ticket(

        summary="Admin should not create customer support tickets.",

        issue_type="general_support",

        priority="low",

        customer_id="CUST001",

    )

 

    assert result["status"] == "denied"

    assert "data" not in result

 

 

def main() -> None:

    tests = [

        test_classify_refund_escalation_request,

        test_decide_escalation,

        test_customer_creates_ticket_for_own_order,

        test_customer_cannot_create_ticket_for_other_customer_order,

        test_support_agent_creates_escalated_ticket_for_customer,

        test_app_admin_cannot_create_ticket,

    ]

 

    for test in tests:

        test()

        print(f"{test.__name__}: passed")

 

    print("All support workflow tool tests passed.")

 

 

if __name__ == "__main__":

    main()