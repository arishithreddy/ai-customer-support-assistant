from __future__ import annotations

 

import re

from pathlib import Path

from typing import Any

 

import yaml

 

 

PROJECT_ROOT = Path(__file__).resolve().parents[2]

WORKFLOW_CONFIG_FILE = PROJECT_ROOT / "configs" / "support_workflow.yaml"

 

 

def load_support_workflow_config() -> dict[str, Any]:

    with WORKFLOW_CONFIG_FILE.open(

        "r",

        encoding="utf-8",

    ) as file:

        config = yaml.safe_load(file)

 

    if not isinstance(config, dict):

        raise ValueError(

            "Support workflow config must be a YAML object."

        )

 

    return config

 

 

def normalize_text(text: str) -> str:

    return re.sub(r"\s+", " ", text.strip().lower())

 

 

def contains_any(

    text: str,

    keywords: list[str],

) -> bool:

    normalized = normalize_text(text)

 

    return any(

        keyword.lower() in normalized

        for keyword in keywords

    )

 

 

class SupportWorkflowClassifier:

    """

    Deterministic support workflow classifier.

 

    This is intentionally rule-based for transparency and testability.

    """

 

    def __init__(self) -> None:

        self.config = load_support_workflow_config()

 

    def classify_issue_type(

        self,

        message: str,

    ) -> str:

        issue_rules = self.config.get(

            "issue_type_keywords",

            {},

        )

 

        for issue_type, keywords in issue_rules.items():

            if contains_any(message, keywords):

                return issue_type

 

        return "general_support"

 

    def classify_priority(

        self,

        message: str,

    ) -> str:

        priority_rules = self.config.get(

            "priority_rules",

            {},

        )

 

        if contains_any(

            message,

            priority_rules.get("high_keywords", []),

        ):

            return "high"

 

        if contains_any(

            message,

            priority_rules.get("medium_keywords", []),

        ):

            return "medium"

 

        return "low"

 

    def classify_sentiment(

        self,

        message: str,

    ) -> str:

        normalized = normalize_text(message)

 

        frustrated_terms = [

            "frustrated",

            "angry",

            "upset",

            "third time",

            "nobody helped",

            "unacceptable",

            "terrible",

            "legal action",

            "chargeback",

        ]

 

        positive_terms = [

            "thanks",

            "thank you",

            "appreciate",

            "helpful",

        ]

 

        if any(term in normalized for term in frustrated_terms):

            return "frustrated"

 

        if any(term in normalized for term in positive_terms):

            return "positive"

 

        return "neutral"

 

    def classify(

        self,

        message: str,

    ) -> dict[str, Any]:

        issue_type = self.classify_issue_type(message)

        priority = self.classify_priority(message)

        sentiment = self.classify_sentiment(message)

 

        return {

            "issue_type": issue_type,

            "priority": priority,

            "sentiment": sentiment,

        }

 

    def decide_escalation(

        self,

        *,

        message: str,

        issue_type: str,

        priority: str,

        sentiment: str,

    ) -> dict[str, Any]:

        escalation_rules = self.config.get(

            "escalation_rules",

            {},

        )

 

        reasons: list[str] = []

 

        if priority in escalation_rules.get(

            "escalate_if_priority",

            [],

        ):

            reasons.append(

                f"Priority is {priority}."

            )

 

        if issue_type in escalation_rules.get(

            "escalate_if_issue_type",

            [],

        ):

            reasons.append(

                f"Issue type {issue_type} requires review."

            )

 

        if sentiment == "frustrated":

            reasons.append(

                "Customer sentiment indicates frustration."

            )

 

        if contains_any(

            message,

            escalation_rules.get("escalate_if_keywords", []),

        ):

            reasons.append(

                "Message contains escalation keyword."

            )

 

        should_escalate = bool(reasons)

 

        return {

            "should_escalate": should_escalate,

            "recommended_status": (

                "escalated"

                if should_escalate

                else "open"

            ),

            "reasons": reasons,

        }