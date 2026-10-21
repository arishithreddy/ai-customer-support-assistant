from backend.agent.graph import (

    MCP_TOOL_PERMISSIONS,

    get_authorized_mcp_tool_names,

)

from backend.agent.identity import (

    resolve_agent_identity,

)

from backend.database.session import SessionLocal

from backend.security.auth import (

    authenticate_user,

    create_access_token,

)


AVAILABLE_MCP_TOOLS = set(

    MCP_TOOL_PERMISSIONS.keys()

)


def get_token(

    username: str,

    password: str,

) -> str:

    with SessionLocal() as session:

        user = authenticate_user(

            session,

            username,

            password,

        )

        assert user is not None

        return create_access_token(user)


def test_customer_tool_visibility() -> None:

    tools = get_authorized_mcp_tool_names(

        "customer",

        AVAILABLE_MCP_TOOLS,

    )

    assert tools == {

        "get_order_status",

        "get_refund_status",

        "get_product_details",

        "get_ticket_status",
        "classfy_support_request",
        "decide_escalation",    
        "create_support_ticket",

    }


def test_support_agent_tool_visibility() -> None:

    tools = get_authorized_mcp_tool_names(

        "support_agent",

        AVAILABLE_MCP_TOOLS,

    )

    assert tools == AVAILABLE_MCP_TOOLS


def test_supervisor_tool_visibility() -> None:

    tools = get_authorized_mcp_tool_names(

        "supervisor",

        AVAILABLE_MCP_TOOLS,

    )

    assert tools == AVAILABLE_MCP_TOOLS


def test_app_admin_tool_visibility() -> None:

    tools = get_authorized_mcp_tool_names(

        "app_admin",

        AVAILABLE_MCP_TOOLS,

    )

    assert tools == {

        "get_product_details"

    }


def test_unknown_role_has_no_mcp_tools() -> None:

    tools = get_authorized_mcp_tool_names(

        "unknown_role",

        AVAILABLE_MCP_TOOLS,

    )

    assert tools == set()


def test_unknown_tool_is_not_exposed() -> None:

    tools = get_authorized_mcp_tool_names(

        "supervisor",

        {

            "get_order_status",

            "unregistered_dangerous_tool",

        },

    )

    assert tools == {

        "get_order_status"

    }


def test_verified_identity_uses_database_role(

    demo_password: str,

) -> None:

    token = get_token(

        "customer_ava",

        demo_password,

    )

    identity = resolve_agent_identity(token)

    assert identity.role == "customer"

    assert identity.customer_id == "CUST001"

    assert identity.identity_subject == (

        "local-customer-ava"

    )


def main() -> None:

    import os

    demo_password = os.getenv(

        "DEMO_USER_PASSWORD",

        "",

    )

    if len(demo_password) < 12:

        raise RuntimeError(

            "Configure DEMO_USER_PASSWORD in .env."

        )

    tests_without_arguments = [

        test_customer_tool_visibility,

        test_support_agent_tool_visibility,

        test_supervisor_tool_visibility,

        test_app_admin_tool_visibility,

        test_unknown_role_has_no_mcp_tools,

        test_unknown_tool_is_not_exposed,

    ]

    for test in tests_without_arguments:

        test()

        print(f"{test.__name__}: passed")

    test_verified_identity_uses_database_role(

        demo_password

    )

    print(

        "test_verified_identity_uses_database_role: "

        "passed"

    )

    print("All agent tool permission tests passed.")


if __name__ == "__main__":

    main()
