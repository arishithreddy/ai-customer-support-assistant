import os
from typing import Any
from mcp.server.fastmcp import FastMCP
from backend.services.support_tool_service import (

    SupportToolService,

)


mcp = FastMCP("customer-support-tools")


def get_service() -> SupportToolService:
    """

    Resolve identity from the trusted MCP host environment.



    The identity is intentionally not a tool argument because tool arguments

    may be selected or influenced by the LLM.

    """

    identity_subject = os.getenv(

        "MCP_IDENTITY_SUBJECT",

        "",

    ).strip()

    if not identity_subject:

        raise RuntimeError(

            "MCP_IDENTITY_SUBJECT is missing. "

            "The MCP host must provide an authenticated identity."

        )

    return SupportToolService(

        identity_subject=identity_subject

    )


@mcp.tool()
def get_order_status(order_id: str) -> dict[str, Any]:
    """Return an authorized and role-filtered order status."""

    return get_service().get_order_status(order_id)


@mcp.tool()
def get_refund_status(refund_id: str) -> dict[str, Any]:
    """Return an authorized and role-filtered refund status."""

    return get_service().get_refund_status(refund_id)


@mcp.tool()
def get_product_details(product_id: str) -> dict[str, Any]:
    """Return non-sensitive product details."""

    return get_service().get_product_details(product_id)


@mcp.tool()
def get_ticket_status(ticket_id: str) -> dict[str, Any]:
    """Return an authorized and role-filtered support ticket status."""

    return get_service().get_ticket_status(ticket_id)


if __name__ == "__main__":

    mcp.run(transport="stdio")
