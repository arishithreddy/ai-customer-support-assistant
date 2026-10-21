from __future__ import annotations


import http
import json

import os

from pathlib import Path

from typing import Any


from dotenv import load_dotenv

from fastapi import Depends, FastAPI, HTTPException, Query, status

from fastapi.middleware.cors import CORSMiddleware

from sqlalchemy import desc, select


from backend.api.dependencies import (

    CurrentUser,

    VerifiedToken,

    get_current_user,

    get_verified_token,

    require_permission,

)

from backend.api.schemas import (

    AuditLogItem,

    AuditLogResponse,

    ChatRequest,

    ChatResponse,

    CurrentUserResponse,

    HealthResponse,

    LoginRequest,

    LoginResponse,

)

from backend.api.session_store import agent_session_store

from backend.database.models import AuditLog

from backend.database.repositories import AuditRepository

from backend.database.session import SessionLocal

from backend.security.auth import authenticate_user, create_access_token


PROJECT_ROOT = Path(__file__).resolve().parents[2]

load_dotenv(PROJECT_ROOT / ".env")


APP_VERSION = "0.13.0"


app = FastAPI(

    title="AI Customer Support Assistant API",

    description=(

        "Authenticated Agentic RAG customer support backend with "

        "MCP tools, RBAC, guardrails, and audit logging."

    ),

    version=APP_VERSION,

)


allowed_origins = os.getenv(

    "CORS_ALLOWED_ORIGINS",

    "http://localhost:8501,http://127.0.0.1:8501",

).split(",")


app.add_middleware(

    CORSMiddleware,

    allow_origins=[

        origin.strip()

        for origin in allowed_origins

        if origin.strip()

    ],

    allow_credentials=True,

    allow_methods=["*"],

    allow_headers=["*"],

)


@app.get(

    "/health",

    response_model=HealthResponse,

)
async def health() -> HealthResponse:

    return HealthResponse(

        status="ok",

        service="ai-customer-support-assistant",

        version=APP_VERSION,

    )


@app.post(

    "/api/v1/auth/login",

    response_model=LoginResponse,

)
async def login(

    request: LoginRequest,

) -> LoginResponse:

    with SessionLocal() as session:

        user = authenticate_user(

            session,

            request.username,

            request.password,

        )

        if user is None:

            AuditRepository.record(

                session,

                actor_user_id=None,

                action="api_login",

                resource_type="auth",

                resource_id=None,

                outcome="denied",

                reason_code="INVALID_CREDENTIALS",

                details={

                    "username_attempted": request.username[:100],

                },

            )

            session.commit()

            raise HTTPException(

                status_code=status.HTTP_401_UNAUTHORIZED,

                detail="Invalid username or password.",

            )

        token = create_access_token(user)

        AuditRepository.record(

            session,

            actor_user_id=user.user_id,

            action="api_login",

            resource_type="auth",

            resource_id=user.user_id,

            outcome="allowed",

            reason_code="LOGIN_SUCCESS",

            details={

                "role": user.role,

            },

        )

        session.commit()

        return LoginResponse(

            access_token=token,

            username=user.username,

            role=user.role,

        )


@app.get(

    "/api/v1/users/me",

    response_model=CurrentUserResponse,

)
async def me(

    current_user: CurrentUser = Depends(get_current_user),

) -> CurrentUserResponse:

    return CurrentUserResponse(

        user_id=current_user.user_id,

        username=current_user.username,

        role=current_user.role,

        customer_id=current_user.customer_id,

    )


@app.post(

    "/api/v1/chat",

    response_model=ChatResponse,

)
async def chat(

    request: ChatRequest,

    verified_token: VerifiedToken = Depends(get_verified_token),

    current_user: CurrentUser = Depends(get_current_user),

) -> ChatResponse:

    try:

        stored_session = await agent_session_store.get_or_create(

            access_token=verified_token.raw_token,

            user_id=current_user.user_id,

            token_id=current_user.token_id,

            session_id=request.session_id,

        )

        answer = await stored_session.runtime.ask(

            request.message

        )

        session_key = agent_session_store.build_key(

            user_id=current_user.user_id,

            token_id=current_user.token_id,

            session_id=request.session_id,

        )

        return ChatResponse(

            answer=answer,

            session_id=session_key,

            username=current_user.username,

            role=current_user.role,

            tools_available=stored_session.runtime.tool_names,

        )

    except HTTPException:

        raise

    except Exception as error:

        with SessionLocal() as session:

            AuditRepository.record(

                session,

                actor_user_id=current_user.user_id,

                action="api_chat",

                resource_type="agent",

                resource_id=None,

                outcome="error",

                reason_code=type(error).__name__,

                details={

                    "role": current_user.role,

                },

            )

            session.commit()

        raise HTTPException(

            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,

            detail=(

                "The assistant could not safely complete the request."

            ),

        )


@app.delete(

    "/api/v1/chat/session",

)
async def clear_current_user_sessions(

    current_user: CurrentUser = Depends(get_current_user),

) -> dict[str, Any]:

    deleted_count = await agent_session_store.clear_user_sessions(

        user_id=current_user.user_id,

    )

    return {

        "status": "success",

        "deleted_sessions": deleted_count,

    }


@app.get(

    "/api/v1/audit/logs",

    response_model=AuditLogResponse,

)
async def get_audit_logs(

    limit: int = Query(

        default=50,

        ge=1,

        le=200,

    ),

    current_user: CurrentUser = Depends(

        require_permission("read_audit_logs")

    ),

) -> AuditLogResponse:

    with SessionLocal() as session:

        statement = (

            select(AuditLog)

            .order_by(desc(AuditLog.created_at))

            .limit(limit)

        )

        logs = list(session.scalars(statement).all())

    items: list[AuditLogItem] = []

    for log in logs:

        try:

            details = json.loads(log.details_json)

            if not isinstance(details, dict):

                details = {}

        except Exception:

            details = {}

        items.append(

            AuditLogItem(

                audit_id=log.audit_id,

                actor_user_id=log.actor_user_id,

                action=log.action,

                resource_type=log.resource_type,

                resource_id=log.resource_id,

                outcome=log.outcome,

                reason_code=log.reason_code,

                details=details,

                created_at=log.created_at,

            )

        )

    return AuditLogResponse(

        count=len(items),

        items=items,

    )


@app.get(

    "/api/v1/debug/session-count",

)
async def session_count(

    current_user: CurrentUser = Depends(get_current_user),

) -> dict[str, Any]:

    count = await agent_session_store.count()

    return {

        "active_sessions": count,

        "requesting_user": current_user.username,

    }