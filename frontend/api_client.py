from __future__ import annotations


from dataclasses import dataclass

from typing import Any


import requests


@dataclass
class ApiClient:

    base_url: str

    access_token: str | None = None

    timeout_seconds: int = 120

    def _headers(self) -> dict[str, str]:

        headers = {

            "Content-Type": "application/json",

        }

        if self.access_token:

            headers["Authorization"] = (

                f"Bearer {self.access_token}"

            )

        return headers

    def health(self) -> dict[str, Any]:

        response = requests.get(

            f"{self.base_url}/health",

            timeout=10,

        )

        response.raise_for_status()

        return response.json()

    def login(

        self,

        username: str,

        password: str,

    ) -> dict[str, Any]:

        response = requests.post(

            f"{self.base_url}/api/v1/auth/login",

            json={

                "username": username,

                "password": password,

            },

            headers=self._headers(),

            timeout=30,

        )

        if response.status_code == 401:

            raise PermissionError(

                "Invalid username or password."

            )

        response.raise_for_status()

        return response.json()

    def me(self) -> dict[str, Any]:

        response = requests.get(

            f"{self.base_url}/api/v1/users/me",

            headers=self._headers(),

            timeout=30,

        )

        response.raise_for_status()

        return response.json()

    def chat(

        self,

        message: str,

        session_id: str | None = None,

    ) -> dict[str, Any]:

        response = requests.post(

            f"{self.base_url}/api/v1/chat",

            json={

                "message": message,

                "session_id": session_id,

            },

            headers=self._headers(),

            timeout=self.timeout_seconds,

        )

        if response.status_code == 401:

            raise PermissionError(

                "Your session expired. Please log in again."

            )

        if response.status_code == 403:

            raise PermissionError(

                "You do not have permission for this action."

            )

        response.raise_for_status()

        return response.json()

    def clear_chat_session(self) -> dict[str, Any]:

        response = requests.delete(

            f"{self.base_url}/api/v1/chat/session",

            headers=self._headers(),

            timeout=30,

        )

        response.raise_for_status()

        return response.json()

    def audit_logs(

        self,

        limit: int = 50,

    ) -> dict[str, Any]:

        response = requests.get(

            f"{self.base_url}/api/v1/audit/logs",

            headers=self._headers(),

            params={

                "limit": limit,

            },

            timeout=30,

        )

        if response.status_code == 403:

            raise PermissionError(

                "Your role cannot access audit logs."

            )

        response.raise_for_status()

        return response.json()
