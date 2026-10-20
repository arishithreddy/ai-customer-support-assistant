from __future__ import annotations


import math

import os

import re

from dataclasses import dataclass

from pathlib import Path

from typing import Any


import yaml

from dotenv import load_dotenv

from langchain_core.documents import Document

from langchain_core.prompts import ChatPromptTemplate

from langchain_openai import ChatOpenAI


from backend.retrieval.hybrid_retriever import (

    SecureHybridRetriever,

    tokenize,

)

from backend.security.rbac import get_allowed_access_levels


PROJECT_ROOT = Path(__file__).resolve().parents[2]

RETRIEVAL_CONFIG_FILE = PROJECT_ROOT / "configs" / "retrieval.yaml"


load_dotenv(PROJECT_ROOT / ".env")


RESTRICTED_CANARIES = {

    "RX-CANARY-7731",

    "FD-CANARY-4420",

}


ROLE_ESCALATION_TERMS = {

    "ignore instructions",

    "ignore previous",

    "act as supervisor",

    "i am supervisor",

    "i am an admin",

    "show restricted",

    "bypass",

}


@dataclass
class RetrievalAttempt:

    attempt_number: int

    query: str

    result_count: int

    quality_score: float

    passed: bool

    reason: str


@dataclass
class SelfHealingRetrievalResult:

    status: str

    selected_query: str

    results: list[dict[str, Any]]

    attempts: list[RetrievalAttempt]

    rewritten_query: str | None

    role: str


def sigmoid(value: float) -> float:

    return 1.0 / (1.0 + math.exp(-value))


def lexical_overlap_score(

    query: str,

    document_text: str,

) -> float:

    query_tokens = set(tokenize(query))

    document_tokens = set(tokenize(document_text))

    if not query_tokens:

        return 0.0

    overlap = query_tokens.intersection(document_tokens)

    return len(overlap) / len(query_tokens)


class SelfHealingRetriever:

    """

    Wraps SecureHybridRetriever with bounded retrieval repair.



    This class does not bypass RBAC. It calls SecureHybridRetriever,

    which already applies role-based access filtering before candidate

    retrieval.

    """

    def __init__(

        self,

        base_retriever: SecureHybridRetriever,

    ) -> None:

        self.base_retriever = base_retriever

        self.config = self._load_config()

    def _load_config(self) -> dict[str, Any]:

        with RETRIEVAL_CONFIG_FILE.open(

            "r",

            encoding="utf-8",

        ) as file:

            return yaml.safe_load(file)

    def analyze_query(

        self,

        query: str,

    ) -> dict[str, Any]:

        lowered = query.lower()

        possible_injection = any(

            term in lowered

            for term in ROLE_ESCALATION_TERMS

        )

        identifiers = re.findall(

            r"\b(?:ORD|REF|TICK|PROD)-\d+\b",

            query.upper(),

        )

        return {

            "possible_prompt_injection": possible_injection,

            "identifiers": identifiers,

            "query_length": len(query),

        }

    def grade_results(

        self,

        query: str,

        results: list[dict[str, Any]],

    ) -> tuple[float, str]:

        if not results:

            return 0.0, "No retrieved evidence."

        top_results = results[:3]

        per_result_scores: list[float] = []

        for result in top_results:

            document: Document = result["document"]

            reranker_score = float(

                result.get("reranker_score", 0.0)

            )

            normalized_reranker = sigmoid(

                reranker_score

            )

            overlap = lexical_overlap_score(

                query,

                document.page_content,

            )

            combined = (

                0.65 * normalized_reranker

                + 0.35 * overlap

            )

            per_result_scores.append(combined)

        average_score = sum(per_result_scores) / len(

            per_result_scores

        )

        result_count_bonus = min(

            len(results) / 5.0,

            1.0,

        ) * 0.05

        final_score = min(

            average_score + result_count_bonus,

            1.0,

        )

        if len(results) < self.config["self_healing"][

            "min_result_count"

        ]:

            return final_score, "Too few retrieved results."

        return final_score, "Retrieved evidence appears usable."

    def _rewrite_query_with_llm(

        self,

        query: str,

        role: str,

        query_analysis: dict[str, Any],

    ) -> str | None:

        healing_config = self.config["self_healing"]

        if not healing_config.get("rewrite_enabled", True):

            return None

        if not os.getenv("OPENAI_API_KEY"):

            return None

        model = ChatOpenAI(

            model=healing_config["rewrite_model_name"],

            temperature=healing_config.get(

                "rewrite_temperature",

                0.0,

            ),

        )

        prompt = ChatPromptTemplate.from_messages(

            [

                (

                    "system",

                    """

You rewrite user questions into short search queries for a customer support knowledge base.

 

Rules:

- Preserve the user's original intent.

- Preserve identifiers such as ORD, REF, TICK, and PROD codes if present.

- Do not add any new facts.

- Do not add or change user role.

- Do not include instructions to bypass access rules.

- Do not ask for restricted information unless the original query explicitly asks about that topic.

- Keep the query concise.

- Return only the rewritten query.

""".strip(),

                ),

                (

                    "human",

                    """

Authenticated role: {role}

 

Original query:

{query}

 

Detected identifiers:

{identifiers}

 

Rewrite the query for retrieval in at most {max_words} words.

""".strip(),

                ),

            ]

        )

        response = (prompt | model).invoke(

            {

                "role": role,

                "query": query,

                "identifiers": ", ".join(

                    query_analysis["identifiers"]

                )

                or "none",

                "max_words": healing_config[

                    "max_rewrite_words"

                ],

            }

        )

        rewritten = response.content.strip()

        rewritten = re.sub(r"\s+", " ", rewritten)

        if not rewritten:

            return None

        if len(rewritten.split()) > healing_config[

            "max_rewrite_words"

        ]:

            rewritten = " ".join(

                rewritten.split()[

                    : healing_config["max_rewrite_words"]

                ]

            )

        if self._rewrite_looks_unsafe(

            original=query,

            rewritten=rewritten,

        ):

            return None

        return rewritten

    @staticmethod
    def _rewrite_looks_unsafe(

        original: str,

        rewritten: str,

    ) -> bool:

        original_lower = original.lower()

        rewritten_lower = rewritten.lower()

        for term in ROLE_ESCALATION_TERMS:

            if (

                term in rewritten_lower

                and term not in original_lower

            ):

                return True

        return False

    @staticmethod
    def _deduplicate_results(

        result_lists: list[list[dict[str, Any]]],

    ) -> list[dict[str, Any]]:

        seen_chunk_ids: set[str] = set()

        merged: list[dict[str, Any]] = []

        for results in result_lists:

            for result in results:

                chunk_id = result["document"].metadata[

                    "chunk_id"

                ]

                if chunk_id in seen_chunk_ids:

                    continue

                seen_chunk_ids.add(chunk_id)

                merged.append(result)

        return sorted(

            merged,

            key=lambda item: item.get(

                "reranker_score",

                0.0,

            ),

            reverse=True,

        )

    def _validate_authorized_results(

        self,

        role: str,

        results: list[dict[str, Any]],

    ) -> None:

        allowed_levels = set(

            get_allowed_access_levels(role)

        )

        for result in results:

            document = result["document"]

            access_level = document.metadata.get(

                "access_level"

            )

            if access_level not in allowed_levels:

                raise PermissionError(

                    "Unauthorized evidence entered self-healing retrieval."

                )

            content = document.page_content

            if access_level != "restricted":

                for canary in RESTRICTED_CANARIES:

                    if canary in content:

                        raise PermissionError(

                            "Restricted canary appeared in unauthorized evidence."

                        )

    def retrieve(

        self,

        query: str,

        role: str,

        *,

        use_hyde: bool = False,

        final_results: int = 5,

    ) -> SelfHealingRetrievalResult:

        query = query.strip()

        if not query:

            raise ValueError("Query cannot be empty.")

        healing_config = self.config["self_healing"]

        query_analysis = self.analyze_query(query)

        attempts: list[RetrievalAttempt] = []

        collected_result_lists: list[list[dict[str, Any]]] = []

        current_query = query

        rewritten_query: str | None = None

        selected_query = query

        max_attempts = int(

            healing_config.get("max_attempts", 2)

        )

        min_quality_score = float(

            healing_config.get("min_quality_score", 0.42)

        )

        for attempt_number in range(1, max_attempts + 1):

            results = self.base_retriever.retrieve(

                query=current_query,

                role=role,

                use_hyde=use_hyde,

                final_results=final_results,

            )

            self._validate_authorized_results(

                role,

                results,

            )

            quality_score, reason = self.grade_results(

                current_query,

                results,

            )

            passed = quality_score >= min_quality_score

            attempts.append(

                RetrievalAttempt(

                    attempt_number=attempt_number,

                    query=current_query,

                    result_count=len(results),

                    quality_score=quality_score,

                    passed=passed,

                    reason=reason,

                )

            )

            collected_result_lists.append(results)

            if passed:

                selected_query = current_query

                break

            if attempt_number >= max_attempts:

                selected_query = current_query

                break

            rewritten_query = self._rewrite_query_with_llm(

                query=query,

                role=role,

                query_analysis=query_analysis,

            )

            if (

                rewritten_query is None

                or rewritten_query.lower() == current_query.lower()

            ):

                selected_query = current_query

                break

            current_query = rewritten_query

        merged_results = self._deduplicate_results(

            collected_result_lists

        )[:final_results]

        self._validate_authorized_results(

            role,

            merged_results,

        )

        status = (

            "success"

            if merged_results

            else "no_evidence"

        )

        return SelfHealingRetrievalResult(

            status=status,

            selected_query=selected_query,

            results=merged_results,

            attempts=attempts,

            rewritten_query=rewritten_query,

            role=role,
        )
