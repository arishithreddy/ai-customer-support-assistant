from __future__ import annotations


import csv

import json

from pathlib import Path

from statistics import mean

from typing import Any


from backend.services.support_tool_service import SupportToolService


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATASET_FILE = PROJECT_ROOT / "evaluation" / "datasets" / "workflow_eval_set.csv"

RESULTS_DIR = PROJECT_ROOT / "evaluation" / "results"

RESULTS_FILE = RESULTS_DIR / "workflow_eval_results.json"


def load_dataset() -> list[dict[str, str]]:

    with DATASET_FILE.open("r", encoding="utf-8-sig", newline="") as file:

        return list(csv.DictReader(file))


def parse_bool(value: str) -> bool:

    return value.strip().lower() == "true"


def evaluate_row(row: dict[str, str]) -> dict[str, Any]:

    message = row["message"]

    identity_subject = row["identity_subject"]

    expected_issue_type = row["expected_issue_type"]

    expected_priority = row["expected_priority"]

    expected_sentiment = row["expected_sentiment"]

    expected_escalation = parse_bool(

        row["expected_escalation"]

    )

    service = SupportToolService(

        identity_subject=identity_subject

    )

    classification_result = service.classify_support_request(

        message

    )

    if classification_result["status"] != "success":

        return {

            "message": message,

            "passed": False,

            "error": classification_result,

        }

    classification = classification_result["data"]

    escalation_result = service.decide_escalation(

        message=message,

        issue_type=classification["issue_type"],

        priority=classification["priority"],

        sentiment=classification["sentiment"],

    )

    if escalation_result["status"] != "success":

        return {

            "message": message,

            "passed": False,

            "error": escalation_result,

        }

    escalation = escalation_result["data"]

    issue_match = (

        classification["issue_type"] == expected_issue_type

    )

    priority_match = (

        classification["priority"] == expected_priority

    )

    sentiment_match = (

        classification["sentiment"] == expected_sentiment

    )

    escalation_match = (

        escalation["should_escalate"] == expected_escalation

    )

    passed = all(

        [

            issue_match,

            priority_match,

            sentiment_match,

            escalation_match,

        ]

    )

    return {

        "message": message,

        "identity_subject": identity_subject,

        "expected": {

            "issue_type": expected_issue_type,

            "priority": expected_priority,

            "sentiment": expected_sentiment,

            "should_escalate": expected_escalation,

        },

        "actual": {

            "issue_type": classification["issue_type"],

            "priority": classification["priority"],

            "sentiment": classification["sentiment"],

            "should_escalate": escalation["should_escalate"],

        },

        "matches": {

            "issue_type": issue_match,

            "priority": priority_match,

            "sentiment": sentiment_match,

            "escalation": escalation_match,

        },

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

        "workflow_pass_rate": pass_rate,

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

    print("\nSupport Workflow Evaluation Summary")

    print("-" * 80)

    print(f"Total cases:      {summary['total_cases']}")

    print(f"Pass rate:        {summary['workflow_pass_rate']:.3f}")
    print(f"Failed cases:     {summary['failed_cases']}")

    print(f"\nSaved: {RESULTS_FILE}")

 

 

if __name__ == "__main__":

    main()