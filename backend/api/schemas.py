from __future__ import annotations


from datetime import datetime

from typing import Any


from pydantic import BaseModel, Field


class LoginRequest(BaseModel):

    username: str = Field(

        min_length=1,

        max_length=100,

    )

    password: str = Field(

        min_length=1,

        max_length=200,

    )


class LoginResponse(BaseModel):

    access_token: str

    token_type: str = "bearer"

    username: str

    role: str


class CurrentUserResponse(BaseModel):

    user_id: str

    username: str

    role: str

    customer_id: str | None


class ChatRequest(BaseModel):

    message: str = Field(

        min_length=1,

        max_length=3000,

    )

    session_id: str | None = Field(

        default=None,

        max_length=100,

        description=(

            "Optional client-provided session ID. If omitted, the API "

            "uses the token ID as the session key."

        ),

    )


class ChatResponse(BaseModel):

    answer: str

    session_id: str

    username: str

    role: str

    tools_available: list[str]


class HealthResponse(BaseModel):

    status: str

    service: str

    version: str


class AuditLogItem(BaseModel):

    audit_id: str

    actor_user_id: str | None

    action: str

    resource_type: str

    resource_id: str | None

    outcome: str

    reason_code: str | None

    details: dict[str, Any]

    created_at: datetime


class AuditLogResponse(BaseModel):

    count: int

    items: list[AuditLogItem]


class ErrorResponse(BaseModel):

    detail: str
