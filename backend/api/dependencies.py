from __future__ import annotations


from dataclasses import dataclass


from fastapi import Depends, HTTPException, status

from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


from backend.database.repositories import UserRepository

from backend.database.session import SessionLocal

from backend.security.auth import (

    AuthenticationError,

    AuthContext,

    verify_access_token,

)

from backend.security.authorization import has_permission


bearer_scheme = HTTPBearer(

    auto_error=False,

)


@dataclass(frozen=True)
class VerifiedToken:

    raw_token: str

    auth_context: AuthContext


@dataclass(frozen=True)
class CurrentUser:

    user_id: str

    username: str

    identity_subject: str

    role: str

    customer_id: str | None

    token_id: str


def get_verified_token(

    credentials: HTTPAuthorizationCredentials | None = Depends(

        bearer_scheme

    ),

) -> VerifiedToken:

    if credentials is None:

        raise HTTPException(

            status_code=status.HTTP_401_UNAUTHORIZED,

            detail="Missing authorization token.",

        )

    if credentials.scheme.lower() != "bearer":

        raise HTTPException(

            status_code=status.HTTP_401_UNAUTHORIZED,

            detail="Invalid authorization scheme.",

        )

    try:

        auth_context = verify_access_token(credentials.credentials)

    except AuthenticationError:

        raise HTTPException(

            status_code=status.HTTP_401_UNAUTHORIZED,

            detail="Invalid or expired authorization token.",

        )

    return VerifiedToken(

        raw_token=credentials.credentials,

        auth_context=auth_context,

    )


def get_auth_context(

    verified_token: VerifiedToken = Depends(get_verified_token),

) -> AuthContext:

    return verified_token.auth_context


def get_current_user(

    verified_token: VerifiedToken = Depends(get_verified_token),

) -> CurrentUser:

    auth_context = verified_token.auth_context

    with SessionLocal() as session:

        user = UserRepository.get_by_identity_subject(

            session,

            auth_context.identity_subject,

        )

        if user is None or not user.is_active:

            raise HTTPException(

                status_code=status.HTTP_401_UNAUTHORIZED,

                detail="Authenticated user is unavailable.",

            )

        return CurrentUser(

            user_id=user.user_id,

            username=user.username,

            identity_subject=user.identity_subject,

            role=user.role,

            customer_id=user.customer_id,

            token_id=auth_context.token_id,

        )


def require_permission(permission: str):

    def dependency(

        current_user: CurrentUser = Depends(get_current_user),

    ) -> CurrentUser:

        if not has_permission(

            current_user.role,

            permission,

        ):

            raise HTTPException(

                status_code=status.HTTP_403_FORBIDDEN,

                detail="Permission denied.",

            )

        return current_user

    return dependency
