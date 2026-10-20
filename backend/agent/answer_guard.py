from __future__ import annotations


import ast

import json

from dataclasses import dataclass

from typing import Any


from langchain_core.messages import BaseMessage, ToolMessage


RESTRICTED_CANARIES = {

    "RX-CANARY-7731",

    "FD-CANARY-4420",

}


@dataclass
class AnswerGuardResult:

    passed: bool

    reasons: list[str]

    available_citations: list[str]


def parse_tool_content(

    content: Any,

) -> dict[str, Any] | None:

    if isinstance(content, dict):

        return content

    if not isinstance(content, str):

        return None

    try:

        parsed = json.loads(content)

        if isinstance(parsed, dict):

            return parsed

    except Exception:

        pass

    try:

        parsed = ast.literal_eval(content)

        if isinstance(parsed, dict):

            return parsed

    except Exception:

        pass

    return None


def extract_knowledge_tool_outputs(

    messages: list[BaseMessage],

) -> list[dict[str, Any]]:

    outputs: list[dict[str, Any]] = []

    for message in messages:

        if not isinstance(message, ToolMessage):

            continue

        if message.name != "search_knowledge_base":

            continue

        parsed = parse_tool_content(message.content)

        if parsed is not None:

            outputs.append(parsed)

    return outputs


def extract_available_citations(

    knowledge_outputs: list[dict[str, Any]],

) -> list[str]:

    citations: list[str] = []

    for output in knowledge_outputs:

        for item in output.get("results", []):

            citation = item.get("citation", {})

            title = citation.get("title")

            section = citation.get("section")

            if title and section:

                citations.append(

                    f"{title} - {section}"

                )

    return sorted(set(citations))


def verify_agent_answer(

    answer: str,

    messages: list[BaseMessage],

) -> AnswerGuardResult:

    reasons: list[str] = []

    for canary in RESTRICTED_CANARIES:

        if canary in answer:

            reasons.append(

                "Restricted canary marker appeared in the answer."

            )

    knowledge_outputs = extract_knowledge_tool_outputs(

        messages

    )

    available_citations = extract_available_citations(

        knowledge_outputs

    )

    used_knowledge = bool(knowledge_outputs)

    if used_knowledge and available_citations:

        answer_lower = answer.lower()

        citation_found = any(

            citation.lower() in answer_lower

            or citation.split(" - ")[0].lower()

            in answer_lower

            for citation in available_citations

        )

        if not citation_found:

            reasons.append(

                "The answer used knowledge-base evidence but did not cite an available source title."

            )

    if used_knowledge:

        total_results = sum(

            int(output.get("result_count", 0))

            for output in knowledge_outputs

        )

        if total_results == 0:

            unsupported_phrases = [

                "according to",

                "the policy says",

                "you are eligible",

                "you can",

                "you should",

            ]

            answer_lower = answer.lower()

            if any(

                phrase in answer_lower

                for phrase in unsupported_phrases

            ):

                reasons.append(

                    "The answer makes policy-like claims despite no retrieved evidence."

                )

    return AnswerGuardResult(

        passed=len(reasons) == 0,

        reasons=reasons,

        available_citations=available_citations,

    )


def build_repair_instruction(

    guard_result: AnswerGuardResult,

) -> str:

    citation_text = (

        "\n".join(

            f"- {citation}"

            for citation in guard_result.available_citations

        )

        if guard_result.available_citations

        else "- No validated citations were available."

    )

    reasons_text = "\n".join(

        f"- {reason}"

        for reason in guard_result.reasons

    )

    return f"""

Your previous answer failed the answer guard.

 

Problems:

{reasons_text}

 

Repair requirements:

- Rewrite the answer using only retrieved tool evidence and authorized tool results.

- If using knowledge-base evidence, cite one or more available source titles and sections exactly.

- Do not invent unsupported policy details.

- Do not mention internal guardrails or hidden checks.

- If evidence is insufficient, say that the available evidence is insufficient and suggest a safe next step.

 

Available citations:

{citation_text}

""".strip()
