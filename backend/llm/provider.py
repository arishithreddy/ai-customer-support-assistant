from __future__ import annotations

 

import os

from pathlib import Path

from typing import Any

 

from dotenv import load_dotenv

 

 

PROJECT_ROOT = Path(__file__).resolve().parents[2]

 

load_dotenv(PROJECT_ROOT / ".env")

 

 

def create_chat_model(

    *,

    provider: str | None = None,

    model_name: str | None = None,

    temperature: float = 0.0,

    **kwargs: Any,

):

    """

    Create a chat model from the configured provider.

 

    Supported providers:

    - google

    - gemini

    - openai

 

    The rest of the application should use this factory instead of

    importing provider-specific models directly.

    """

    selected_provider = (

        provider

        or os.getenv("LLM_PROVIDER", "google")

    ).strip().lower()

 

    if selected_provider in {"google", "gemini"}:

        from langchain_google_genai import ChatGoogleGenerativeAI

 

        google_api_key = os.getenv("GOOGLE_API_KEY", "").strip()

 

        if not google_api_key:

            raise RuntimeError(

                "GOOGLE_API_KEY is missing. Add it to your .env file."

            )

 

        selected_model = (

            model_name

            or os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

        )

 

        return ChatGoogleGenerativeAI(

            model=selected_model,

            temperature=temperature,

            google_api_key=google_api_key,

            **kwargs,

        )

 

    if selected_provider == "openai":

        from langchain_openai import ChatOpenAI

 

        openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()

 

        if not openai_api_key:

            raise RuntimeError(

                "OPENAI_API_KEY is missing. Add it to your .env file."

            )

 

        selected_model = (

            model_name

            or os.getenv("OPENAI_MODEL", "gpt-4o-mini")

        )

 

        return ChatOpenAI(

            model=selected_model,

            temperature=temperature,

            api_key=openai_api_key,

            **kwargs,

        )

 

    raise ValueError(

        f"Unsupported LLM provider: {selected_provider}. "

        "Use 'google', 'gemini', or 'openai'."

    )