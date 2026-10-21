import json

from datetime import datetime, timezone

from typing import Any, Optional

from uuid import uuid4


from sqlalchemy import select

from sqlalchemy.orm import Session, joinedload


from backend.database.models import (

    AppUser,

    AuditLog,

    Order,

    Product,

    Refund,

    SupportTicket,

)


def cents_to_dollars(cents: int) -> str:

    return f"{cents / 100:.2f}"


class UserRepository:

    @staticmethod
    def get_by_user_id(

        session: Session,

        user_id: str,

    ) -> Optional[AppUser]:

        return session.get(AppUser, user_id)

    @staticmethod
    def get_by_identity_subject(

        session: Session,

        identity_subject: str,

    ) -> Optional[AppUser]:

        statement = select(AppUser).where(

            AppUser.identity_subject == identity_subject

        )

        return session.scalar(statement)


class OrderRepository:

    @staticmethod
    def get_by_id(

        session: Session,

        order_id: str,

    ) -> Optional[Order]:

        statement = (

            select(Order)

            .options(

                joinedload(Order.customer),

                joinedload(Order.product),

            )

            .where(Order.order_id == order_id)

        )

        return session.scalar(statement)

    @staticmethod
    def to_internal_dict(order: Order) -> dict[str, Any]:
        """

        Internal representation only.



        Do not return this directly to customers. The MCP service layer will

        apply ownership checks and role-specific field selection.

        """

        return {

            "order_id": order.order_id,

            "customer_id": order.customer_id,

            "customer_name": order.customer.customer_name,

            "product_id": order.product_id,

            "product_name": order.product.product_name,

            "order_status": order.order_status,

            "order_date": order.order_date.isoformat(),

            "ship_date": (

                order.ship_date.isoformat()

                if order.ship_date

                else None

            ),

            "delivery_date": (

                order.delivery_date.isoformat()

                if order.delivery_date

                else None

            ),

            "shipping_method": order.shipping_method,

            "carrier": order.carrier,

            "tracking_status": order.tracking_status,

            "total_amount": cents_to_dollars(

                order.total_amount_cents

            ),

        }


class RefundRepository:

    @staticmethod
    def get_by_id(

        session: Session,

        refund_id: str,

    ) -> Optional[Refund]:

        statement = (

            select(Refund)

            .options(

                joinedload(Refund.customer),

                joinedload(Refund.order),

            )

            .where(Refund.refund_id == refund_id)

        )

        return session.scalar(statement)

    @staticmethod
    def get_for_order(

        session: Session,

        order_id: str,

    ) -> list[Refund]:

        statement = (

            select(Refund)

            .where(Refund.order_id == order_id)

            .order_by(Refund.requested_date.desc())

        )

        return list(session.scalars(statement).all())


class ProductRepository:

    @staticmethod
    def get_by_id(

        session: Session,

        product_id: str,

    ) -> Optional[Product]:

        return session.get(Product, product_id)


class TicketRepository:

    @staticmethod
    def get_by_id(

        session: Session,

        ticket_id: str,

    ) -> Optional[SupportTicket]:

        return session.get(SupportTicket, ticket_id)

    @staticmethod
    def get_for_customer(

        session: Session,

        customer_id: str,

    ) -> list[SupportTicket]:

        statement = (

            select(SupportTicket)

            .where(SupportTicket.customer_id == customer_id)

            .order_by(SupportTicket.created_at.desc())

        )

        return list(session.scalars(statement).all())

    @staticmethod
    def create(

        session: Session,

        *,

        ticket_id: str,

        customer_id: str,

        order_id: Optional[str],

        issue_type: str,

        priority: str,

        status: str,

        created_at,

        last_updated,

        summary: str,

    ) -> SupportTicket:

        ticket = SupportTicket(

            ticket_id=ticket_id,

            customer_id=customer_id,

            order_id=order_id,

            issue_type=issue_type,

            priority=priority,

            status=status,

            created_at=created_at,

            last_updated=last_updated,

            summary=summary,

        )

        session.add(ticket)

        return ticket


class AuditRepository:

    @staticmethod
    def record(

        session: Session,

        *,

        actor_user_id: Optional[str],

        action: str,

        resource_type: str,

        resource_id: Optional[str],

        outcome: str,

        reason_code: Optional[str] = None,

        details: Optional[dict[str, Any]] = None,

    ) -> AuditLog:
        """

        Store only redacted metadata in `details`.



        Do not store raw prompts, access tokens, full tool responses,

        customer addresses, or payment information.

        """

        event = AuditLog(

            audit_id=f"AUD-{uuid4().hex}",

            actor_user_id=actor_user_id,

            action=action,

            resource_type=resource_type,

            resource_id=resource_id,

            outcome=outcome,

            reason_code=reason_code,

            details_json=json.dumps(details or {}),

            created_at=datetime.now(timezone.utc),

        )

        session.add(event)

        return event
