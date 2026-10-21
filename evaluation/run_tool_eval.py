from __future__ import annotations


import csv

import json

from pathlib import Path

from statistics import mean

from typing import Any


from backend.agent.graph import (

    MCP_TOOL_PERMISSIONS,

    get_authorized_mcp_tool_names,

)

from backend.database.session import SessionLocal

from backend.security.auth import authenticate_user


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATASET_FILE = PROJECT_ROOT / "evaluation" / "datasets" / "tool_eval_set.csv"

RESULTS_DIR = PROJECT_ROOT / "evaluation" / "results"

RESULTS_FILE = RESULTS_DIR / "tool_eval_results.json"


def load_dataset() -> list[dict[str, str]]:

    with DATASET_FILE.open("r", encoding="utf-8-sig", newline="") as file:

        return list(csv.DictReader(file))


def get_user_role(username: str) -> str:

    import os

    password = os.getenv("DEMO_USER_PASSWORD", "")

    with SessionLocal() as session:

        user = authenticate_user(

            session,

            username,

            password,

        )

        if user is None:

            raise RuntimeError(

                f"Could not authenticate test user: {username}"

            )

        return user.role


def parse_tools(tool_string: str) -> set[str]:

    if not tool_string.strip():

        return set()

    return {

        item.strip()

        for item in tool_string.split("|")

        if item.strip()

    }


def evaluate_row(row: dict[str, str]) -> dict[str, Any]:

    username = row["username"]

    role = get_user_role(username)

    expected_tools = parse_tools(

        row["expected_tools"]

    )

    available_mcp_tools = set(MCP_TOOL_PERMISSIONS.keys())

    authorized_mcp_tools = get_authorized_mcp_tool_names(

        role,

        available_mcp_tools,

    )

    # search_knowledge_base is not an MCP tool, but it is available

    # to all authenticated agent roles.

    available_agent_tools = set(authorized_mcp_tools)

    available_agent_tools.add("search_knowledge_base")

    missing_expected = expected_tools - available_agent_tools

    unexpected_exposure = set()

    if role == "app_admin":

        forbidden = {

            "get_order_status",

            "get_refund_status",

            "get_ticket_status",

            "create_support_ticket",

            "classify_support_request",

            "decide_escalation",

        }

        unexpected_exposure = forbidden.intersection(

            available_agent_tools

        )

    passed = (

        not missing_expected

        and not unexpected_exposure

    )

    return {

        "query": row["query"],

        "username": username,

        "role": role,

        "expected_tools": sorted(expected_tools),

        "available_agent_tools": sorted(available_agent_tools),

        "missing_expected": sorted(missing_expected),

        "unexpected_exposure": sorted(unexpected_exposure),

        "passed": passed,

    }


def main() -> None:

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    dataset = load_dataset()

    rows = [

        evaluate_row(row)

        for row in dataset

    ]

    pass_rate = mean(

        1.0 if row["passed"] else 0.0

        for row in rows

    )

    summary = {

        "total_cases": len(rows),

        "tool_visibility_pass_rate": pass_rate,

        "failed_cases": sum(

            1 for row in rows if not row["passed"]

        ),

    }

    output = {

        "summary": summary,

        "rows": rows,

    }

    RESULTS_FILE.write_text(

        json.dumps(output, indent=2),

        encoding="utf-8",

    )

    print("\nTool Visibility Evaluation Summary")

    print("-" * 80)

    print(f"Total cases:      {summary['total_cases']}")

    print(f"Pass rate:        {summary['tool_visibility_pass_rate']:.3f}")

    print(f"Failed cases:     {summary['failed_cases']}")
    print(f"Results written to:   {RESULTS_FILE}")

if __name__ == "__main__":  
    main()
