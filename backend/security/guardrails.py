from __future__ import annotations


import re

from dataclasses import dataclass

from pathlib import Path

from typing import Any

import yaml

 

 

PROJECT_ROOT = Path(__file__).resolve().parents[2]

GUARDRAILS_CONFIG_FILE = PROJECT_ROOT / "configs" / "guardrails.yaml"

 

 

RESTRICTED_CANARIES = {

    "RX-CANARY-7731",

    "FD-CANARY-4420",

}

 

 

PROMPT_INJECTION_PATTERNS = [

    r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions",

    r"disregard\s+(all\s+)?(previous|prior|above)\s+instructions",

    r"reveal\s+(the\s+)?system\s+prompt",

    r"show\s+(me\s+)?(the\s+)?system\s+prompt",

    r"print\s+(the\s+)?hidden\s+instructions",

    r"developer\s+message",

    r"hidden\s+rules",

    r"you\s+are\s+now\s+in\s+developer\s+mode",

    r"jailbreak",

]

 

ROLE_ESCALATION_PATTERNS = [

    r"\bi\s+am\s+(now\s+)?(a\s+)?supervisor\b",

    r"\bi\s+am\s+(now\s+)?(an\s+)?admin\b",

    r"\bi\s+am\s+(now\s+)?(an\s+)?app_admin\b",

    r"\bact\s+as\s+(a\s+)?supervisor\b",

    r"\bact\s+as\s+(an\s+)?admin\b",

    r"\bchange\s+my\s+role\b",

    r"\bupgrade\s+my\s+role\b",

    r"\bbypass\s+(rbac|access|authorization|permissions)\b",

]

 

SECRET_EXTRACTION_PATTERNS = [

    r"\bapi[_-]?key\b",

    r"\bsecret[_-]?key\b",

    r"\baccess[_-]?token\b",

    r"\bjwt\b",

    r"\bpassword\b",

    r"\bprivate\s+key\b",

    r"\benvironment\s+variable",

    r"\b\.env\b",

]

 

EMAIL_PATTERN = re.compile(

    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"

)

 

PHONE_PATTERN = re.compile(

    r"(?<!\d)(?:\+?\d[\d\s().-]{7,}\d)(?!\d)"

)

 

JWT_PATTERN = re.compile(

    r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b"

)

 

SECRET_ASSIGNMENT_PATTERN = re.compile(

    r"(?i)\b(?:api[_-]?key|secret[_-]?key|token|password)\s*[:=]\s*['\"]?[^'\"\s]{8,}"

)

 

PAYMENT_CARD_PATTERN = re.compile(

    r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)"

)

 

 

@dataclass(frozen=True)

class GuardrailFinding:

    category: str

    severity: str

    message: str

 

 

@dataclass(frozen=True)

class GuardrailResult:

    blocked: bool

    risk_score: float

    findings: list[GuardrailFinding]

    sanitized_text: str

def load_guardrails_config() -> dict[str, Any]:

    with GUARDRAILS_CONFIG_FILE.open(

        "r",

        encoding="utf-8",

    ) as file:

        config = yaml.safe_load(file)

    if not isinstance(config, dict):

        raise ValueError(

            "Guardrails config must be a YAML object."

        )

    return config


def normalize_text(text: str) -> str:

    return re.sub(r"\s+", " ", text.strip())


def luhn_check(number: str) -> bool:

    digits = [int(char) for char in number if char.isdigit()]

    if len(digits) < 13 or len(digits) > 19:

        return False

    checksum = 0

    parity = len(digits) % 2

    for index, digit in enumerate(digits):

        if index % 2 == parity:

            digit *= 2

            if digit > 9:

                digit -= 9

        checksum += digit

    return checksum % 10 == 0


def contains_payment_card_like_value(text: str) -> bool:
    # ---------------------------------------------------------
    # Normal card numbers
    # ---------------------------------------------------------
    for match in PAYMENT_CARD_PATTERN.findall(text):
        candidate = re.sub(r"\D", "", match)

        if 13 <= len(candidate) <= 19 and luhn_check(candidate):
            return True

    # ---------------------------------------------------------
    # Masked card numbers
    #
    # Examples:
    # ***************1111
    # **** **** **** 1111
    # XXXX XXXX XXXX 1111
    # ---------------------------------------------------------
    masked_card_pattern = re.compile(
        r"(?i)"
        r"(?:\*{4,}|x{4,})"
        r"(?:[\s-]*(?:\*{4,}|x{4,}))?"
        r"[\s-]*\d{4}\b"
    )

    if masked_card_pattern.search(text):
        return True

    return False


def redact_sensitive_text(text: str) -> str:

    config = load_guardrails_config()

    redaction = config.get("redaction", {})

    sanitized = text

    sanitized = JWT_PATTERN.sub(

        redaction.get("jwt", "[REDACTED_TOKEN]"),

        sanitized,

    )

    sanitized = SECRET_ASSIGNMENT_PATTERN.sub(

        lambda match: match.group(0).split("=")[0]

        + "="

        + redaction.get("secret", "[REDACTED_SECRET]")

        if "=" in match.group(0)

        else redaction.get("secret", "[REDACTED_SECRET]"),

        sanitized,

    )

    sanitized = EMAIL_PATTERN.sub(

        redaction.get("email", "[REDACTED_EMAIL]"),

        sanitized,

    )

    sanitized = PHONE_PATTERN.sub(

        redaction.get("phone", "[REDACTED_PHONE]"),

        sanitized,

    )

    def replace_card(match: re.Match[str]) -> str:

        candidate = re.sub(r"\D", "", match.group(0))

        if luhn_check(candidate):

            return redaction.get(

                "payment_card",

                "[REDACTED_PAYMENT_CARD]",

            )

        return match.group(0)

    sanitized = PAYMENT_CARD_PATTERN.sub(

        replace_card,

        sanitized,

    )

    return sanitized


def pattern_matches(

    text: str,

    patterns: list[str],

) -> bool:

    lowered = text.lower()

    return any(

        re.search(pattern, lowered, flags=re.IGNORECASE)

        for pattern in patterns

    )


def evaluate_user_input(
    text: str,
    role: str,
) -> GuardrailResult:
    config = load_guardrails_config()
    input_config = config.get("input_guardrails", {})
    thresholds = config.get("risk_thresholds", {})

    normalized = normalize_text(text)
    sanitized = redact_sensitive_text(normalized)

    findings: list[GuardrailFinding] = []
    risk_score = 0.0
    hard_block = False

    # ---------------------------------------------------------
    # Prompt injection
    # ---------------------------------------------------------
    if input_config.get("block_prompt_injection", True) and pattern_matches(
        normalized,
        PROMPT_INJECTION_PATTERNS,
    ):
        findings.append(
            GuardrailFinding(
                category="prompt_injection",
                severity="high",
                message="Prompt-injection language detected.",
            )
        )
        risk_score += 0.45
        hard_block = True

    # ---------------------------------------------------------
    # Role escalation
    # ---------------------------------------------------------
    if input_config.get("block_role_escalation", True) and pattern_matches(
        normalized,
        ROLE_ESCALATION_PATTERNS,
    ):
        findings.append(
            GuardrailFinding(
                category="role_escalation",
                severity="high",
                message="Attempted role escalation detected.",
            )
        )
        risk_score += 0.45
        hard_block = True

    # ---------------------------------------------------------
    # Secret extraction
    # ---------------------------------------------------------
    if input_config.get("block_secret_extraction", True) and pattern_matches(
        normalized,
        SECRET_EXTRACTION_PATTERNS,
    ):
        findings.append(
            GuardrailFinding(
                category="secret_extraction",
                severity="high",
                message="Secret or token extraction language detected.",
            )
        )
        risk_score += 0.35
        hard_block = True

    # ---------------------------------------------------------
    # Payment card
    # ---------------------------------------------------------
    if input_config.get(
        "block_payment_card_like_values",
        True,
    ) and contains_payment_card_like_value(normalized):
        findings.append(
            GuardrailFinding(
                category="payment_card",
                severity="high",
                message="Payment-card-like value detected.",
            )
        )
        risk_score += 0.85

    # ---------------------------------------------------------
    # Email PII
    # ---------------------------------------------------------
    if EMAIL_PATTERN.search(normalized):
        findings.append(
            GuardrailFinding(
                category="pii_email",
                severity="medium",
                message="Email address detected and redacted for logs.",
            )
        )
        risk_score += 0.15

    # ---------------------------------------------------------
    # Phone PII
    # ---------------------------------------------------------
    if PHONE_PATTERN.search(normalized):
        findings.append(
            GuardrailFinding(
                category="pii_phone",
                severity="medium",
                message="Phone number detected and redacted for logs.",
            )
        )
        risk_score += 0.15

    # ---------------------------------------------------------
    # Final risk calculation
    # ---------------------------------------------------------
    risk_score = min(risk_score, 1.0)

    block_score = float(
        thresholds.get("block_score", 0.75)
    )

    # Hard security violations are blocked immediately.
    # Other risks are blocked when their combined score
    # reaches the configured threshold.
    blocked = hard_block or risk_score >= block_score

    return GuardrailResult(
        blocked=blocked,
        risk_score=risk_score,
        findings=findings,
        sanitized_text=sanitized,
    )


def evaluate_agent_output(

    text: str,

    role: str,

) -> GuardrailResult:

    config = load_guardrails_config()

    output_config = config.get("output_guardrails", {})

    sanitized = text

    findings: list[GuardrailFinding] = []

    risk_score = 0.0

    if output_config.get("redact_pii", True):

        redacted = redact_sensitive_text(sanitized)

        if redacted != sanitized:

            findings.append(

                GuardrailFinding(

                    category="output_pii_redacted",

                    severity="medium",

                    message="PII-like content was redacted from output.",

                )

            )

            risk_score += 0.25

        sanitized = redacted

    if output_config.get("block_restricted_canaries", True):

        for canary in RESTRICTED_CANARIES:

            if canary in sanitized:

                findings.append(

                    GuardrailFinding(

                        category="restricted_canary",

                        severity="critical",

                        message="Restricted canary appeared in output.",

                    )

                )

                risk_score = 1.0

                sanitized = sanitized.replace(

                    canary,

                    "[REDACTED_RESTRICTED_MARKER]",

                )

    blocked = risk_score >= 1.0

    return GuardrailResult(

        blocked=blocked,

        risk_score=risk_score,

        findings=findings,

        sanitized_text=sanitized,

    )


def findings_to_dicts(

    findings: list[GuardrailFinding],

) -> list[dict[str, str]]:

    return [

        {

            "category": finding.category,

            "severity": finding.severity,

            "message": finding.message,

        }

        for finding in findings

    ]
