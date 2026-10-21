from __future__ import annotations


import asyncio

from dataclasses import dataclass

from datetime import datetime, timezone


from backend.agent.graph import AgentRuntime, create_agent_runtime


@dataclass
class StoredAgentSession:

    runtime: AgentRuntime

    user_id: str

    created_at: datetime

    last_used_at: datetime


class AgentSessionStore:

    """

    In-memory session store for local development.



    This should be replaced by a persistent/session-aware store for

    production deployments.

    """

    def __init__(self) -> None:

        self._sessions: dict[str, StoredAgentSession] = {}

        self._lock = asyncio.Lock()

    @staticmethod
    def build_key(

        *,

        user_id: str,

        token_id: str,

        session_id: str | None,

    ) -> str:

        safe_session_id = session_id or token_id

        return f"{user_id}:{safe_session_id}"

    async def get_or_create(

        self,

        *,

        access_token: str,

        user_id: str,

        token_id: str,

        session_id: str | None,

    ) -> StoredAgentSession:

        key = self.build_key(

            user_id=user_id,

            token_id=token_id,

            session_id=session_id,

        )

        async with self._lock:

            existing = self._sessions.get(key)

            if existing is not None:

                existing.last_used_at = datetime.now(

                    timezone.utc

                )

                return existing

            runtime = await create_agent_runtime(

                access_token=access_token,

                thread_id=key,

            )

            stored = StoredAgentSession(

                runtime=runtime,

                user_id=user_id,

                created_at=datetime.now(timezone.utc),

                last_used_at=datetime.now(timezone.utc),

            )

            self._sessions[key] = stored

            return stored

    async def delete_user_session(

        self,

        *,

        user_id: str,

        token_id: str,

        session_id: str | None,

    ) -> bool:

        key = self.build_key(

            user_id=user_id,

            token_id=token_id,

            session_id=session_id,

        )

        async with self._lock:

            return self._sessions.pop(key, None) is not None

    async def clear_user_sessions(

        self,

        *,

        user_id: str,

    ) -> int:

        async with self._lock:

            keys_to_delete = [

                key

                for key, value in self._sessions.items()

                if value.user_id == user_id

            ]

            for key in keys_to_delete:

                self._sessions.pop(key, None)

            return len(keys_to_delete)

    async def count(self) -> int:

        async with self._lock:

            return len(self._sessions)


agent_session_store = AgentSessionStore()
