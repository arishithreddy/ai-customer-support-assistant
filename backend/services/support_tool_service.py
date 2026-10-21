from __future__ import annotations

from backend.security.authorization import has_permission
from typing import Any, Optional
from datetime import datetime, timezone
from uuid import uuid4

from backend.services.support_workflow import SupportWorkflowClassifier


from sqlalchemy.orm import Session


from backend.database.models import AppUser, Order, Refund, SupportTicket

from backend.database.repositories import (

    AuditRepository,

    OrderRepository,

    ProductRepository,

    RefundRepository,

    TicketRepository,

    UserRepository,

)

from backend.database.session import SessionLocal


GENERIC_DENIAL_MESSAGE = (

    "This record is not available for the authenticated account."

)


STAFF_DATA_ROLES = {

    "support_agent",

    "supervisor",

}


def mask_name(name: str) -> str:
    """

    Mask a person's name for roles that do not require the full value.



    Example:

        Ava Thompson -> A** T*******

    """

    parts = name.strip().split()

    masked_parts = []

    for part in parts:

        if not part:

            continue

        if len(part) == 1:

            masked_parts.append("*")

        else:

            masked_parts.append(

                part[0] + ("*" * (len(part) - 1))

            )

    return " ".join(masked_parts)


class SupportToolService:

    """

    Authorization-aware service used by MCP tools.



    Security decisions happen here rather than inside the LLM.

    """

    def __init__(self, identity_subject: str):

        self.identity_subject = identity_subject.strip()

        if not self.identity_subject:

            raise ValueError(

                "A verified identity subject is required."

            )

    def _get_actor(

        self,

        session: Session,

    ) -> Optional[AppUser]:

        actor = UserRepository.get_by_identity_subject(

            session,

            self.identity_subject,

        )

        if actor is None or not actor.is_active:

            return None

        return actor

    def _record_audit(

        self,

        session: Session,

        *,

        actor: Optional[AppUser],

        action: str,

        resource_type: str,

        resource_id: Optional[str],

        outcome: str,

        reason_code: str,

    ) -> None:

        AuditRepository.record(

            session,

            actor_user_id=actor.user_id if actor else None,

            action=action,

            resource_type=resource_type,

            resource_id=resource_id,

            outcome=outcome,

            reason_code=reason_code,

            details={

                "authentication_source": "local_mcp_identity",

            },

        )

    @staticmethod
    def _has_permission(actor: AppUser, permission: str) -> bool:
        """
        Check if the actor has the specified permission.
        """
        return has_permission(actor.role, permission)

    @staticmethod
    def _can_access_customer_record(

        actor: AppUser,

        record_customer_id: str,

    ) -> bool:
        """

        Customers can access only records they own.



        Support agents and supervisors can access customer-support records.

        Application administrators are intentionally excluded.

        """

        if actor.role == "customer":

            return actor.customer_id == record_customer_id

        return actor.role in STAFF_DATA_ROLES

    @staticmethod
    def _format_order(

        actor: AppUser,

        order: Order,

    ) -> dict[str, Any]:

        base_result: dict[str, Any] = {

            "order_id": order.order_id,

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

        }

        if actor.role == "support_agent":

            base_result.update(

                {

                    "customer_id": order.customer_id,

                    "customer_name": mask_name(

                        order.customer.customer_name

                    ),

                }

            )

        elif actor.role == "supervisor":

            base_result.update(

                {

                    "customer_id": order.customer_id,

                    "customer_name": order.customer.customer_name,

                    "total_amount": (

                        f"{order.total_amount_cents / 100:.2f}"

                    ),

                }

            )

        return base_result

    @staticmethod
    def _format_refund(

        actor: AppUser,

        refund: Refund,

    ) -> dict[str, Any]:

        result: dict[str, Any] = {

            "refund_id": refund.refund_id,

            "order_id": refund.order_id,

            "refund_status": refund.refund_status,

            "refund_reason": refund.refund_reason,

            "requested_date": refund.requested_date.isoformat(),

            "approved_date": (

                refund.approved_date.isoformat()

                if refund.approved_date

                else None

            ),

            "processed_date": (

                refund.processed_date.isoformat()

                if refund.processed_date

                else None

            ),

            "refund_amount": (

                f"{refund.refund_amount_cents / 100:.2f}"

            ),

        }

        if actor.role == "support_agent":

            result["customer_id"] = refund.customer_id

            result["customer_name"] = mask_name(

                refund.customer.customer_name

            )

        elif actor.role == "supervisor":

            result["customer_id"] = refund.customer_id

            result["customer_name"] = (

                refund.customer.customer_name

            )

        return result

    @staticmethod
    def _format_ticket(

        actor: AppUser,

        ticket: SupportTicket,

    ) -> dict[str, Any]:

        result: dict[str, Any] = {

            "ticket_id": ticket.ticket_id,

            "order_id": ticket.order_id,

            "issue_type": ticket.issue_type,

            "priority": ticket.priority,

            "status": ticket.status,

            "created_at": ticket.created_at.isoformat(),

            "last_updated": ticket.last_updated.isoformat(),

            "summary": ticket.summary,

        }

        if actor.role in STAFF_DATA_ROLES:

            result["customer_id"] = ticket.customer_id

        return result

    def get_order_status(

        self,

        order_id: str,

    ) -> dict[str, Any]:

        order_id = order_id.strip().upper()

        with SessionLocal() as session:

            actor = self._get_actor(session)

            if actor is None:

                self._record_audit(

                    session,

                    actor=None,

                    action="read_order",

                    resource_type="order",

                    resource_id=order_id,

                    outcome="denied",

                    reason_code="INVALID_OR_INACTIVE_IDENTITY",

                )

                session.commit()

                return {

                    "status": "denied",

                    "message": GENERIC_DENIAL_MESSAGE,

                }

            if not self._has_permission(actor, "read_order"):

                self._record_audit(

                    session,

                    actor=actor,

                    action="read_order",

                    resource_type="order",

                    resource_id=order_id,

                    outcome="denied",

                    reason_code="ROLE_PERMISSION_DENIED",

                )

                session.commit()

                return {

                    "status": "denied",

                    "message": GENERIC_DENIAL_MESSAGE,

                }

            order = OrderRepository.get_by_id(

                session,

                order_id,

            )

            # Use the same denial response for missing and unauthorized

            # records to reduce identifier-enumeration risk.

            if order is None:

                self._record_audit(

                    session,

                    actor=actor,

                    action="read_order",

                    resource_type="order",

                    resource_id=order_id,

                    outcome="denied",

                    reason_code="NOT_FOUND_OR_NOT_AUTHORIZED",

                )

                session.commit()

                return {

                    "status": "denied",

                    "message": GENERIC_DENIAL_MESSAGE,

                }

            if not self._can_access_customer_record(

                actor,

                order.customer_id,

            ):

                self._record_audit(

                    session,

                    actor=actor,

                    action="read_order",

                    resource_type="order",

                    resource_id=order_id,

                    outcome="denied",

                    reason_code="NOT_FOUND_OR_NOT_AUTHORIZED",

                )

                session.commit()

                return {

                    "status": "denied",

                    "message": GENERIC_DENIAL_MESSAGE,

                }

            result = self._format_order(actor, order)

            self._record_audit(

                session,

                actor=actor,

                action="read_order",

                resource_type="order",

                resource_id=order_id,

                outcome="allowed",

                reason_code="AUTHORIZED",

            )

            session.commit()

            return {

                "status": "success",

                "data": result,

            }

    def get_refund_status(

        self,

        refund_id: str,

    ) -> dict[str, Any]:

        refund_id = refund_id.strip().upper()

        with SessionLocal() as session:

            actor = self._get_actor(session)

            if actor is None:

                self._record_audit(

                    session,

                    actor=None,

                    action="read_refund",

                    resource_type="refund",

                    resource_id=refund_id,

                    outcome="denied",

                    reason_code="INVALID_OR_INACTIVE_IDENTITY",

                )

                session.commit()

                return {

                    "status": "denied",

                    "message": GENERIC_DENIAL_MESSAGE,

                }

            if not self._has_permission(actor, "read_refund"):

                self._record_audit(

                    session,

                    actor=actor,

                    action="read_refund",

                    resource_type="refund",

                    resource_id=refund_id,

                    outcome="denied",

                    reason_code="ROLE_PERMISSION_DENIED",

                )

                session.commit()

                return {

                    "status": "denied",

                    "message": GENERIC_DENIAL_MESSAGE,

                }

            refund = RefundRepository.get_by_id(

                session,

                refund_id,

            )

            if (

                refund is None

                or not self._can_access_customer_record(

                    actor,

                    refund.customer_id,

                )

            ):

                self._record_audit(

                    session,

                    actor=actor,

                    action="read_refund",

                    resource_type="refund",

                    resource_id=refund_id,

                    outcome="denied",

                    reason_code="NOT_FOUND_OR_NOT_AUTHORIZED",

                )

                session.commit()

                return {

                    "status": "denied",

                    "message": GENERIC_DENIAL_MESSAGE,

                }

            result = self._format_refund(actor, refund)

            self._record_audit(

                session,

                actor=actor,

                action="read_refund",

                resource_type="refund",

                resource_id=refund_id,

                outcome="allowed",

                reason_code="AUTHORIZED",

            )

            session.commit()

            return {

                "status": "success",

                "data": result,

            }

    def get_product_details(

        self,

        product_id: str,

    ) -> dict[str, Any]:

        product_id = product_id.strip().upper()

        with SessionLocal() as session:

            actor = self._get_actor(session)

            if actor is None:

                self._record_audit(

                    session,

                    actor=None,

                    action="read_product",

                    resource_type="product",

                    resource_id=product_id,

                    outcome="denied",

                    reason_code="INVALID_OR_INACTIVE_IDENTITY",

                )

                session.commit()

                return {

                    "status": "denied",

                    "message": "Product information is unavailable.",

                }

            if not self._has_permission(actor, "read_product"):

                self._record_audit(

                    session,

                    actor=actor,

                    action="read_product",

                    resource_type="product",

                    resource_id=product_id,

                    outcome="denied",

                    reason_code="ROLE_PERMISSION_DENIED",

                )

                session.commit()

                return {

                    "status": "denied",

                    "message": "Product information is unavailable.",

                }

            product = ProductRepository.get_by_id(

                session,

                product_id,

            )

            if product is None:

                self._record_audit(

                    session,

                    actor=actor,

                    action="read_product",

                    resource_type="product",

                    resource_id=product_id,

                    outcome="denied",

                    reason_code="NOT_FOUND",

                )

                session.commit()

                return {

                    "status": "not_found",

                    "message": "Product information is unavailable.",

                }

            result = {

                "product_id": product.product_id,

                "product_name": product.product_name,

                "category": product.category,

                "warranty_months": product.warranty_months,

                "returnable": product.returnable,

                "is_digital": product.is_digital,

            }

            self._record_audit(

                session,

                actor=actor,

                action="read_product",

                resource_type="product",

                resource_id=product_id,

                outcome="allowed",

                reason_code="AUTHORIZED",

            )

            session.commit()

            return {

                "status": "success",

                "data": result,

            }

    def get_ticket_status(

        self,

        ticket_id: str,

    ) -> dict[str, Any]:

        ticket_id = ticket_id.strip().upper()

        with SessionLocal() as session:

            actor = self._get_actor(session)

            if actor is None:

                self._record_audit(

                    session,

                    actor=None,

                    action="read_ticket",

                    resource_type="ticket",

                    resource_id=ticket_id,

                    outcome="denied",

                    reason_code="INVALID_OR_INACTIVE_IDENTITY",

                )

                session.commit()

                return {

                    "status": "denied",

                    "message": GENERIC_DENIAL_MESSAGE,

                }

            if not self._has_permission(actor, "read_ticket"):

                self._record_audit(

                    session,

                    actor=actor,

                    action="read_ticket",

                    resource_type="ticket",

                    resource_id=ticket_id,

                    outcome="denied",

                    reason_code="ROLE_PERMISSION_DENIED",

                )

                session.commit()

                return {

                    "status": "denied",

                    "message": GENERIC_DENIAL_MESSAGE,

                }

            ticket = TicketRepository.get_by_id(

                session,

                ticket_id,

            )

            if (

                ticket is None

                or not self._can_access_customer_record(

                    actor,

                    ticket.customer_id,

                )

            ):

                self._record_audit(

                    session,

                    actor=actor,

                    action="read_ticket",

                    resource_type="ticket",

                    resource_id=ticket_id,

                    outcome="denied",

                    reason_code="NOT_FOUND_OR_NOT_AUTHORIZED",

                )

                session.commit()

                return {

                    "status": "denied",

                    "message": GENERIC_DENIAL_MESSAGE,

                }

            result = self._format_ticket(actor, ticket)

            self._record_audit(

                session,

                actor=actor,

                action="read_ticket",

                resource_type="ticket",

                resource_id=ticket_id,

                outcome="allowed",

                reason_code="AUTHORIZED",

            )

            session.commit()

            return {

                "status": "success",

                "data": result,
            }

    def classify_support_request(

        self,

        message: str,

    ) -> dict[str, Any]:

        message = message.strip()

 

        if not message:

            return {

                "status": "error",

                "message": "Support message cannot be empty.",

            }

 

        with SessionLocal() as session:

            actor = self._get_actor(session)

 

            if actor is None:

                self._record_audit(

                    session,

                    actor=None,

                    action="classify_support_request",

                    resource_type="support_request",

                    resource_id=None,

                    outcome="denied",

                    reason_code="INVALID_OR_INACTIVE_IDENTITY",

                )

                session.commit()

 

                return {

                    "status": "denied",

                    "message": "Unable to classify this request.",

                }

 

            if not self._has_permission(

                actor,

                "classify_support_request",

            ):

                self._record_audit(

                    session,

                    actor=actor,

                    action="classify_support_request",

                    resource_type="support_request",

                    resource_id=None,

                    outcome="denied",

                    reason_code="ROLE_PERMISSION_DENIED",

                )

                session.commit()

 

                return {

                    "status": "denied",

                    "message": "Unable to classify this request.",

                }

 

            classifier = SupportWorkflowClassifier()

            classification = classifier.classify(message)

 

            self._record_audit(

                session,

                actor=actor,

                action="classify_support_request",

                resource_type="support_request",

                resource_id=None,

                outcome="allowed",

                reason_code="AUTHORIZED",

            )

            session.commit()

 

            return {

                "status": "success",

                "data": classification,

            }

 

    def decide_escalation(

        self,

        message: str,

        issue_type: str,

        priority: str,

        sentiment: str,

    ) -> dict[str, Any]:

        message = message.strip()

        issue_type = issue_type.strip()

        priority = priority.strip().lower()

        sentiment = sentiment.strip().lower()

 

        with SessionLocal() as session:

            actor = self._get_actor(session)

 

            if actor is None:

                self._record_audit(

                    session,

                    actor=None,

                    action="decide_escalation",

                    resource_type="support_request",

                    resource_id=None,

                    outcome="denied",

                    reason_code="INVALID_OR_INACTIVE_IDENTITY",

                )

                session.commit()

 

                return {

                    "status": "denied",

                    "message": "Unable to evaluate escalation.",

                }

 

            if not self._has_permission(

                actor,

                "decide_escalation",

            ):

                self._record_audit(

                    session,

                    actor=actor,

                    action="decide_escalation",

                    resource_type="support_request",

                    resource_id=None,

                    outcome="denied",

                    reason_code="ROLE_PERMISSION_DENIED",

                )

                session.commit()

 

                return {

                    "status": "denied",

                    "message": "Unable to evaluate escalation.",

                }

 

            classifier = SupportWorkflowClassifier()

 

            decision = classifier.decide_escalation(

                message=message,

                issue_type=issue_type,

                priority=priority,

                sentiment=sentiment,

            )

 

            safe_decision = {

                "should_escalate": decision["should_escalate"],

                "recommended_status": decision["recommended_status"],

                "reasons": decision["reasons"],

            }

 

            self._record_audit(

                session,

                actor=actor,

                action="decide_escalation",

                resource_type="support_request",

                resource_id=None,

                outcome="allowed",

                reason_code="AUTHORIZED",

            )

            session.commit()

 

            return {

                "status": "success",

                "data": safe_decision,

            }

 

    def create_support_ticket(

        self,

        summary: str,

        issue_type: str,

        priority: str,

        order_id: str | None = None,

        customer_id: str | None = None,

        escalate: bool = False,

    ) -> dict[str, Any]:

        summary = summary.strip()

        issue_type = issue_type.strip().lower()

        priority = priority.strip().lower()

 

        order_id = (

            order_id.strip().upper()

            if order_id and order_id.strip()

            else None

        )

 

        requested_customer_id = (

            customer_id.strip().upper()

            if customer_id and customer_id.strip()

            else None

        )

 

        if not summary:

            return {

                "status": "error",

                "message": "Ticket summary cannot be empty.",

            }

 

        if priority not in {"low", "medium", "high"}:

            return {

                "status": "error",

                "message": "Priority must be low, medium, or high.",

            }

 

        with SessionLocal() as session:

            actor = self._get_actor(session)

 

            if actor is None:

                self._record_audit(

                    session,

                    actor=None,

                    action="create_support_ticket",

                    resource_type="ticket",

                    resource_id=None,

                    outcome="denied",

                    reason_code="INVALID_OR_INACTIVE_IDENTITY",

                )

                session.commit()

 

                return {

                    "status": "denied",

                    "message": "Unable to create a support ticket.",

                }

 

            if not self._has_permission(

                actor,

                "create_support_ticket",

            ):

                self._record_audit(

                    session,

                    actor=actor,

                    action="create_support_ticket",

                    resource_type="ticket",

                    resource_id=None,

                    outcome="denied",

                    reason_code="ROLE_PERMISSION_DENIED",

                )

                session.commit()

 

                return {

                    "status": "denied",

                    "message": "Unable to create a support ticket.",

                }

 

            if actor.role == "customer":

                resolved_customer_id = actor.customer_id

 

                if resolved_customer_id is None:

                    self._record_audit(

                        session,

                        actor=actor,

                        action="create_support_ticket",

                        resource_type="ticket",

                        resource_id=None,

                        outcome="denied",

                        reason_code="CUSTOMER_ID_MISSING",

                    )

                    session.commit()

 

                    return {

                        "status": "denied",

                        "message": "Unable to create a support ticket.",

                    }

 

            elif actor.role in STAFF_DATA_ROLES:

                if not requested_customer_id:

                    self._record_audit(

                        session,

                        actor=actor,

                        action="create_support_ticket",

                        resource_type="ticket",

                        resource_id=None,

                        outcome="denied",

                        reason_code="CUSTOMER_ID_REQUIRED_FOR_STAFF",

                    )

                    session.commit()

 

                    return {

                        "status": "error",

                        "message": (

                            "customer_id is required when staff create "

                            "a ticket for a customer."

                        ),

                    }

 

                resolved_customer_id = requested_customer_id

 

            else:

                self._record_audit(

                    session,

                    actor=actor,

                    action="create_support_ticket",

                    resource_type="ticket",

                    resource_id=None,

                    outcome="denied",

                    reason_code="ROLE_PERMISSION_DENIED",

                )

                session.commit()

 

                return {

                    "status": "denied",

                    "message": "Unable to create a support ticket.",

                }

 

            if order_id:

                order = OrderRepository.get_by_id(

                    session,

                    order_id,

                )

 

                if (

                    order is None

                    or order.customer_id != resolved_customer_id

                ):

                    self._record_audit(

                        session,

                        actor=actor,

                        action="create_support_ticket",

                        resource_type="ticket",

                        resource_id=None,

                        outcome="denied",

                        reason_code="ORDER_NOT_FOUND_OR_NOT_AUTHORIZED",

                    )

                    session.commit()

 

                    return {

                        "status": "denied",

                        "message": (

                            "Unable to create a support ticket for "

                            "that order."

                        ),

                    }

 

            status = "escalated" if escalate else "open"

            now = datetime.now(timezone.utc)

            ticket_id = f"TICK-{uuid4().hex[:8].upper()}"

 

            ticket = TicketRepository.create(

                session,

                ticket_id=ticket_id,

                customer_id=resolved_customer_id,

                order_id=order_id,

                issue_type=issue_type,

                priority=priority,

                status=status,

                created_at=now,

                last_updated=now,

                summary=summary[:1000],

            )

 

            self._record_audit(

                session,

                actor=actor,

                action="create_support_ticket",

                resource_type="ticket",

                resource_id=ticket.ticket_id,

                outcome="allowed",

                reason_code="AUTHORIZED",

            )

 

            session.commit()

 

            response_data: dict[str, Any] = {

                "ticket_id": ticket.ticket_id,

                "issue_type": ticket.issue_type,

                "priority": ticket.priority,

                "status": ticket.status,

                "order_id": ticket.order_id,

                "created_at": ticket.created_at.isoformat(),

            }

 

            if actor.role in STAFF_DATA_ROLES:

                response_data["customer_id"] = ticket.customer_id

 

            return {

                "status": "success",

                "data": response_data,

            }