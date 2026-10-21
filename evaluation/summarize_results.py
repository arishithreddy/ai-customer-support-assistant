from __future__ import annotations


import json

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

RESULTS_DIR = PROJECT_ROOT / "evaluation" / "results"


RESULT_FILES = [

    "retrieval_eval_results.json",

    "tool_eval_results.json",

    "security_eval_results.json",

    "workflow_eval_results.json",

]


def main() -> None:

    print("\nEvaluation Summary")

    print("=" * 80)

    for file_name in RESULT_FILES:

        file_path = RESULTS_DIR / file_name

        if not file_path.exists():

            print(f"\n{file_name}: missing")

            continue

        data = json.loads(

            file_path.read_text(encoding="utf-8")

        )

        summary = data.get("summary", {})

        print(f"\n{file_name}")

        print("-" * 80)

        for key, value in summary.items():

            if isinstance(value, float):

                print(f"{key}: {value:.3f}")

            else:

                print(f"{key}: {value}")

if __name__ == "__main__":

    main()
