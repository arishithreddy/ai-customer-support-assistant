from __future__ import annotations

 

import csv

import json

import time

from pathlib import Path

from statistics import mean

from typing import Any

 

from backend.retrieval.hybrid_retriever import SecureHybridRetriever

 

 

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATASET_FILE = PROJECT_ROOT / "evaluation" / "datasets" / "retrieval_eval_set.csv"

RESULTS_DIR = PROJECT_ROOT / "evaluation" / "results"

RESULTS_FILE = RESULTS_DIR / "retrieval_eval_results.json"

 

 

def load_dataset() -> list[dict[str, str]]:

    with DATASET_FILE.open("r", encoding="utf-8-sig", newline="") as file:

        return list(csv.DictReader(file))

 

 

def evaluate_row(

    retriever: SecureHybridRetriever,

    row: dict[str, str],

) -> dict[str, Any]:

    query = row["query"]

    role = row["role"]

    expected_doc_id = row["expected_doc_id"].strip()

    expected_access_level = row["expected_access_level"].strip()

 

    start = time.perf_counter()

 

    results = retriever.retrieve(

        query=query,

        role=role,

        use_hyde=False,

        final_results=5,

    )

 

    latency_ms = (time.perf_counter() - start) * 1000

 

    returned_doc_ids = [

        result["document"].metadata["doc_id"]

        for result in results

    ]

 

    returned_access_levels = [

        result["document"].metadata["access_level"]

        for result in results

    ]

 

    top_doc_id = returned_doc_ids[0] if returned_doc_ids else None

 

    expected_found = (

        expected_doc_id in returned_doc_ids

        if expected_doc_id

        else True

    )

 

    top1_match = (

        top_doc_id == expected_doc_id

        if expected_doc_id

        else True

    )

 

    unauthorized_restricted_seen = (

        role != "supervisor"

        and "restricted" in returned_access_levels

    )

 

    access_level_violation = False

 

    if role == "customer":

        access_level_violation = any(

            level != "public"

            for level in returned_access_levels

        )

 

    elif role in {"support_agent", "app_admin"}:

        access_level_violation = any(

            level == "restricted"

            for level in returned_access_levels

        )

 

    return {

        "query": query,

        "role": role,

        "expected_doc_id": expected_doc_id,

        "top_doc_id": top_doc_id,

        "returned_doc_ids": returned_doc_ids,

        "returned_access_levels": returned_access_levels,

        "expected_found_at_5": expected_found,

        "top1_match": top1_match,

        "unauthorized_restricted_seen": unauthorized_restricted_seen,

        "access_level_violation": access_level_violation,

        "latency_ms": latency_ms,

    }

 

 

def main() -> None:

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

 

    dataset = load_dataset()

    retriever = SecureHybridRetriever()

 

    rows = [

        evaluate_row(retriever, row)

        for row in dataset

    ]

 

    recall_at_5 = mean(

        1.0 if row["expected_found_at_5"] else 0.0

        for row in rows

    )

 

    top1_accuracy = mean(

        1.0 if row["top1_match"] else 0.0

        for row in rows

    )

 

    security_violations = sum(

        1

        for row in rows

        if row["access_level_violation"]

        or row["unauthorized_restricted_seen"]

    )

 

    avg_latency_ms = mean(

        row["latency_ms"]

        for row in rows

    )

 

    summary = {

        "total_cases": len(rows),

        "recall_at_5": recall_at_5,

        "top1_accuracy": top1_accuracy,

        "security_violations": security_violations,

        "avg_latency_ms": avg_latency_ms,

    }

 

    output = {

        "summary": summary,

        "rows": rows,

    }

 

    RESULTS_FILE.write_text(

        json.dumps(output, indent=2),

        encoding="utf-8",

    )

 

    print("\nRetrieval Evaluation Summary")

    print("-" * 80)

    print(f"Total cases:          {summary['total_cases']}")

    print(f"Recall@5:             {summary['recall_at_5']:.3f}")

    print(f"Top-1 accuracy:       {summary['top1_accuracy']:.3f}")

    print(f"Security violations:  {summary['security_violations']}")

    print(f"Avg latency ms:       {summary['avg_latency_ms']:.1f}")

    print(f"\nSaved: {RESULTS_FILE}")

 

 

if __name__ == "__main__":

    main()