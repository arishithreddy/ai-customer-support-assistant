import os

from typing import Any


from mcp.server.fastmcp import FastMCP


from backend.security.auth import (

    AuthenticationError,

    verify_access_token,

)

from backend.services.support_tool_service import (

    SupportToolService,

)


mcp = FastMCP("customer-support-tools")


def get_service() -> SupportToolService:
    """

    Verify the JWT supplied by the trusted local MCP host.



    The token is not an MCP tool argument, so the LLM cannot choose or

    modify the authenticated identity.

    """

    access_token = os.getenv(

        "MCP_ACCESS_TOKEN",

        "",

    ).strip()

    if not access_token:

        raise RuntimeError(

            "MCP_ACCESS_TOKEN is missing. "

            "Authenticate before starting the MCP server."

        )

    try:

        auth_context = verify_access_token(

            access_token

        )

    except AuthenticationError as error:

        raise RuntimeError(

            "MCP authentication failed."

        ) from error

    return SupportToolService(

        identity_subject=auth_context.identity_subject

    )


@mcp.tool()
def get_order_status(

    order_id: str,

) -> dict[str, Any]:
    """Return an authorized and role-filtered order status."""

    return get_service().get_order_status(order_id)


@mcp.tool()
def get_refund_status(

    refund_id: str,

) -> dict[str, Any]:
    """Return an authorized and role-filtered refund status."""

    return get_service().get_refund_status(refund_id)


@mcp.tool()
def get_product_details(

    product_id: str,

) -> dict[str, Any]:
    """Return authorized non-sensitive product details."""

    return get_service().get_product_details(product_id)


@mcp.tool()
def get_ticket_status(

    ticket_id: str,

) -> dict[str, Any]:
    """Return an authorized and role-filtered ticket status."""

    return get_service().get_ticket_status(ticket_id)

@mcp.tool()

def classify_support_request(

    message: str,

) -> dict[str, Any]:

    """Classify a support message into issue type, priority, and sentiment."""

    return get_service().classify_support_request(message)

 

 

@mcp.tool()

def decide_escalation(

    message: str,

    issue_type: str,

    priority: str,

    sentiment: str,

) -> dict[str, Any]:

    """Decide whether a support request should be escalated."""

    return get_service().decide_escalation(

        message=message,

        issue_type=issue_type,

        priority=priority,

        sentiment=sentiment,

    )

 

 

@mcp.tool()

def create_support_ticket(

    summary: str,

    issue_type: str,

    priority: str,

    order_id: str | None = None,

    customer_id: str | None = None,

    escalate: bool = False,

) -> dict[str, Any]:

    """Create an authorized support ticket."""

    return get_service().create_support_ticket(

        summary=summary,

        issue_type=issue_type,

        priority=priority,

        order_id=order_id,

        customer_id=customer_id,

        escalate=escalate,

    )




if __name__ == "__main__":

    mcp.run(transport="stdio")
