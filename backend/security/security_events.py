from __future__ import annotations

 

from typing import Any

 

from backend.database.models import AppUser

from backend.database.repositories import AuditRepository

from backend.database.session import SessionLocal

from backend.security.guardrails import (

    GuardrailResult,

    findings_to_dicts,

)

 

 

def record_guardrail_event(

    *,

    actor_user_id: str | None,

    action: str,

    outcome: str,

    reason_code: str,

    guardrail_result: GuardrailResult,

    resource_type: str = "agent_message",

    resource_id: str | None = None,

    extra_details: dict[str, Any] | None = None,

) -> None:

    details = {

        "risk_score": guardrail_result.risk_score,

        "findings": findings_to_dicts(

            guardrail_result.findings

        ),

        "sanitized_preview": guardrail_result.sanitized_text[:500],

    }

 

    if extra_details:

        details.update(extra_details)

 

    with SessionLocal() as session:

        AuditRepository.record(

            session,

            actor_user_id=actor_user_id,

            action=action,

            resource_type=resource_type,

            resource_id=resource_id,

            outcome=outcome,

            reason_code=reason_code,

            details=details,

        )

 

        session.commit()

 

 

def record_agent_security_event(

    *,

    actor: AppUser | None,

    action: str,

    outcome: str,

    reason_code: str,

    details: dict[str, Any] | None = None,

) -> None:

    with SessionLocal() as session:

        AuditRepository.record(

            session,

            actor_user_id=actor.user_id if actor else None,

            action=action,

            resource_type="agent",

            resource_id=None,

            outcome=outcome,

            reason_code=reason_code,

            details=details or {},

        )

 

        session.commit()