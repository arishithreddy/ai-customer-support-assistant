from __future__ import annotations

 

import csv

import json

from pathlib import Path

from statistics import mean

from typing import Any

 

from backend.security.guardrails import (

    evaluate_agent_output,

    evaluate_user_input,

)

 

 

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATASET_FILE = PROJECT_ROOT / "evaluation" / "datasets" / "security_redteam_set.csv"

RESULTS_DIR = PROJECT_ROOT / "evaluation" / "results"

RESULTS_FILE = RESULTS_DIR / "security_eval_results.json"

 

 

def load_dataset() -> list[dict[str, str]]:

    with DATASET_FILE.open("r", encoding="utf-8-sig", newline="") as file:

        return list(csv.DictReader(file))

 

 

def parse_bool(value: str) -> bool:

    return value.strip().lower() == "true"

 

 

def parse_forbidden_terms(value: str) -> list[str]:

    if not value.strip():

        return []

 

    return [

        item.strip()

        for item in value.split("|")

        if item.strip()

    ]

 

 

def evaluate_row(row: dict[str, str]) -> dict[str, Any]:

    prompt = row["prompt"]

    expected_blocked = parse_bool(

        row["expected_blocked"]

    )

    forbidden_terms = parse_forbidden_terms(

        row["forbidden_terms"]

    )

 

    # This is a deterministic guardrail-level evaluation.

    # It does not call the full LLM agent.

    input_result = evaluate_user_input(

        prompt,

        role="customer",

    )

 

    blocked_correct = (

        input_result.blocked == expected_blocked

    )

 

    output_result = evaluate_agent_output(

        prompt,

        role="customer",

    )

 

    sanitized_text = output_result.sanitized_text

 

    forbidden_leaks = [

        term

        for term in forbidden_terms

        if term and term in sanitized_text

    ]

 

    no_forbidden_leak = len(forbidden_leaks) == 0

 

    passed = blocked_correct and no_forbidden_leak

 

    return {

        "prompt": prompt,

        "expected_blocked": expected_blocked,

        "actual_blocked": input_result.blocked,

        "risk_score": input_result.risk_score,

        "findings": [

            finding.category

            for finding in input_result.findings

        ],

        "forbidden_terms": forbidden_terms,

        "forbidden_leaks": forbidden_leaks,

        "blocked_correct": blocked_correct,

        "no_forbidden_leak": no_forbidden_leak,

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

 

    leak_count = sum(

        1

        for row in rows

        if not row["no_forbidden_leak"]

    )

 

    summary = {

        "total_cases": len(rows),

        "security_pass_rate": pass_rate,

        "forbidden_leak_count": leak_count,

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

 

    print("\nSecurity Guardrail Evaluation Summary")

    print("-" * 80)

    print(f"Total cases:          {summary['total_cases']}")

    print(f"Pass rate:            {summary['security_pass_rate']:.3f}")

    print(f"Forbidden leaks:      {summary['forbidden_leak_count']}")

    print(f"Failed cases:         {summary['failed_cases']}")
    print(f"Results written to:   {RESULTS_FILE}")

if __name__ == "__main__":  
    main()