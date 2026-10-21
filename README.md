Evaluation Summary
================================================================================

retrieval_eval_results.json: missing

tool_eval_results.json
--------------------------------------------------------------------------------
total_cases: 11
tool_visibility_pass_rate: 0.909
failed_cases: 1

security_eval_results.json
--------------------------------------------------------------------------------
total_cases: 9
security_pass_rate: 0.778
forbidden_leak_count: 1
failed_cases: 2

workflow_eval_results.json
--------------------------------------------------------------------------------
total_cases: 6
workflow_pass_rate: 0.833
failed_cases: 1
---------------------------------------------------------------------------------------------------------------------------------
MAIN


Retrieval Evaluation Summary
--------------------------------------------------------------------------------
Total cases:          11
Recall@5:             1.000
Top-1 accuracy:       1.000
Security violations:  0
Avg latency ms:       347.1

Saved: C:\Users\A.Rishith Reddy\Downloads\ai-customer-support-rag-assistant\evaluation\results\retrieval_eval_results.json

Running: C:\Users\A.Rishith Reddy\Downloads\ai-customer-support-rag-assistant\.venv\Scripts\python.exe -m evaluation.run_tool_eval
--------------------------------------------------------------------------------

Tool Visibility Evaluation Summary
--------------------------------------------------------------------------------
Total cases:      11
Pass rate:        0.909
Failed cases:     1
Results written to:   C:\Users\A.Rishith Reddy\Downloads\ai-customer-support-rag-assistant\evaluation\results\tool_eval_results.json

Running: C:\Users\A.Rishith Reddy\Downloads\ai-customer-support-rag-assistant\.venv\Scripts\python.exe -m evaluation.run_security_eval
--------------------------------------------------------------------------------

Security Guardrail Evaluation Summary
--------------------------------------------------------------------------------
Total cases:          9
Pass rate:            0.778
Forbidden leaks:      1
Failed cases:         2
Results written to:   C:\Users\A.Rishith Reddy\Downloads\ai-customer-support-rag-assistant\evaluation\results\security_eval_results.json

Running: C:\Users\A.Rishith Reddy\Downloads\ai-customer-support-rag-assistant\.venv\Scripts\python.exe -m evaluation.run_workflow_eval
--------------------------------------------------------------------------------

Support Workflow Evaluation Summary
--------------------------------------------------------------------------------
Total cases:      6
Pass rate:        0.833
Failed cases:     1
