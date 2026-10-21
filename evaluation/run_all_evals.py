from __future__ import annotations

import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


EVAL_COMMANDS = [
    [
        sys.executable,
        "-m",
        "evaluation.run_retrieval_eval",
    ],
    [
        sys.executable,
        "-m",
        "evaluation.run_tool_eval",
    ],
    [
        sys.executable,
        "-m",
        "evaluation.run_security_eval",
    ],
    [
        sys.executable,
        "-m",
        "evaluation.run_workflow_eval",
    ],
]


def main() -> None:
    print("\nRunning all deterministic evaluations")
    print("=" * 80)

    for command in EVAL_COMMANDS:
        print(f"\nRunning: {' '.join(command)}")
        print("-" * 80)

        completed = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            check=False,
        )

        if completed.returncode != 0:
            raise SystemExit(
                f"Evaluation failed: {' '.join(command)}"
            )

    print("\nAll deterministic evaluations completed.")


if __name__ == "__main__":
    main()