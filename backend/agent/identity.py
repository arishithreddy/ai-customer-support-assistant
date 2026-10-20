from dataclasses import dataclass

from typing import Optional


from backend.database.repositories import UserRepository

from backend.database.session import SessionLocal

from backend.security.auth import (

    AuthenticationError,

    verify_access_token,

)


ALLOWED_AGENT_ROLES = {

    "customer",

    "support_agent",

    "supervisor",

    "app_admin",

}


@dataclass(frozen=True)
class AgentIdentity:

    user_id: str

    identity_subject: str

    username: str

    role: str

    customer_id: Optional[str]

    token_id: str


def resolve_agent_identity(

    access_token: str,

) -> AgentIdentity:
    """

    Verify a JWT and resolve the current application user.



    The role and customer mapping are loaded from the database instead

    of being trusted from token claims or user messages.

    """

    auth_context = verify_access_token(access_token)

    with SessionLocal() as session:

        user = UserRepository.get_by_identity_subject(

            session,

            auth_context.identity_subject,

        )

        if user is None or not user.is_active:

            raise AuthenticationError(

                "Authenticated user is unavailable."

            )

        if user.role not in ALLOWED_AGENT_ROLES:

            raise AuthenticationError(

                "Authenticated user has an invalid role."

            )

        return AgentIdentity(

            user_id=user.user_id,

            identity_subject=user.identity_subject,

            username=user.username,

            role=user.role,

            customer_id=user.customer_id,

            token_id=auth_context.token_id,

        )
