"""
Deliverability Engine & Compliance Validator
============================================
Enforces 2026 cold email deliverability best practices, spam-score reduction,
and compliance guardrails (CAN-SPAM, GDPR, India DPDP Act).

Key Capabilities:
1. Spam-trigger word & deceptive formatting detection.
2. Cold outreach word count optimizer (under 120 words for primary inbox placement).
3. Opt-out & physical address compliance verification.
4. Sending cadence & randomized delay calculation (90-240s interval).
5. Hard-bounce & permanent suppression management.
"""

import re
import random
from typing import Dict, Any, List, Set, Tuple

# Deceptive or spam-trigger words and phrases to avoid in subject/body
SPAM_TRIGGER_PATTERNS = [
    r"\bfree\b",
    r"\bguaranteed\b",
    r"\bact now\b",
    r"\blimited time\b",
    r"\burgent\b",
    r"\b100%\b",
    r"\brisk-free\b",
    r"\bno obligation\b",
    r"\bclick here\b",
    r"\bbest price\b",
    r"\bunbeatable\b",
    r"\bwinner\b",
    r"\bcash bonus\b"
]

EXCESSIVE_PUNCTUATION_RE = re.compile(r"(!{2,}|\?{2,})")
ALL_CAPS_WORD_RE = re.compile(r"\b[A-Z]{4,}\b")
DECEPTIVE_PREFIX_RE = re.compile(r"^(re:\s*|fwd:\s*)", re.IGNORECASE)
OPT_OUT_PATTERNS = [
    r"opt[ -]?out",
    r"unsubscribe",
    r"reply\s+['\"]?no['\"]?",
    r"let me know and i will not write again",
    r"reply to remove"
]


class DeliverabilityResult:
    def __init__(self, is_valid: bool, score: int, warnings: List[str], word_count: int):
        self.is_valid = is_valid
        self.score = score  # 0 to 100
        self.warnings = warnings
        self.word_count = word_count

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "deliverability_score": self.score,
            "warnings": self.warnings,
            "word_count": self.word_count
        }


def check_spam_triggers(text: str) -> List[str]:
    """Scans text for aggressive promotional or spam-trigger phrases."""
    found = []
    text_lower = text.lower()
    for pattern in SPAM_TRIGGER_PATTERNS:
        if re.search(pattern, text_lower):
            found.append(f"Trigger phrase detected: '{pattern.replace(r'\b', '')}'")

    if EXCESSIVE_PUNCTUATION_RE.search(text):
        found.append("Excessive punctuation detected ('!!' or '??')")

    all_caps_matches = ALL_CAPS_WORD_RE.findall(text)
    # Ignore acceptable acronyms like HTML, CSS, PHP, CRM, ERP, API, INR
    allowed_acronyms = {"HTML", "CSS", "PHP", "CRM", "ERP", "API", "INR", "AMC", "JSON", "REST", "SaaS"}
    bad_caps = [w for w in all_caps_matches if w not in allowed_acronyms]
    if len(bad_caps) > 1:
        found.append(f"Excessive ALL-CAPS words: {', '.join(bad_caps[:3])}")

    return found


def has_opt_out_mechanism(body: str) -> bool:
    """Checks if email body includes a clear opt-out statement."""
    body_lower = body.lower()
    return any(re.search(p, body_lower) for p in OPT_OUT_PATTERNS)


def has_physical_address(body: str) -> bool:
    """Checks if email includes physical business address for CAN-SPAM compliance."""
    body_lower = body.lower()
    indicators = ["ahmedabad", "gujarat", "india", "location:", "address:"]
    return any(ind in body_lower for ind in indicators)


def validate_email_deliverability(subject: str, body: str, is_first_contact: bool = True) -> DeliverabilityResult:
    """
    Validates email subject and body for primary inbox deliverability and legal compliance.
    Calculates a deliverability health score from 0 to 100.
    """
    warnings = []
    deductions = 0

    # 1. Subject line checks
    if DECEPTIVE_PREFIX_RE.match(subject.strip()) and is_first_contact:
        warnings.append("Misleading 'Re:' or 'Fwd:' prefix on cold introductory email.")
        deductions += 30

    subject_triggers = check_spam_triggers(subject)
    if subject_triggers:
        warnings.extend([f"Subject: {t}" for t in subject_triggers])
        deductions += 25 * len(subject_triggers)

    if subject.isupper():
        warnings.append("Subject is entirely ALL-CAPS.")
        deductions += 30

    # 2. Body spam trigger checks
    body_triggers = check_spam_triggers(body)
    if body_triggers:
        warnings.extend([f"Body: {t}" for t in body_triggers])
        deductions += 15 * len(body_triggers)

    # 3. Word count check (Cold emails should stay concise, ideally under 120 words)
    words = re.findall(r"\b\w+\b", body)
    word_count = len(words)
    if word_count > 150:
        warnings.append(f"Email body is long ({word_count} words). Recommended <120 words for cold intro.")
        deductions += 10
    elif word_count < 15:
        warnings.append("Email body is unusually short (<15 words).")
        deductions += 15

    # 4. Compliance checks
    if not has_opt_out_mechanism(body):
        warnings.append("Missing explicit opt-out mechanism ('Reply no to opt out').")
        deductions += 20

    if not has_physical_address(body):
        warnings.append("Missing physical business location / address (CAN-SPAM requirement).")
        deductions += 15

    # 5. Link density check
    links = re.findall(r"https?://[^\s]+", body)
    if len(links) > 2:
        warnings.append(f"Too many links ({len(links)}). Max 1-2 links recommended on initial outreach.")
        deductions += 15

    score = max(0, 100 - deductions)
    is_valid = score >= 50

    return DeliverabilityResult(
        is_valid=is_valid,
        score=score,
        warnings=warnings,
        word_count=word_count
    )


def calculate_safe_delay(cadence_stage: str = "stable") -> float:
    """
    Returns a randomized polite delay in seconds between consecutive emails:
    - stable: 90 to 240 seconds
    - warmup: 240 to 600 seconds
    - test: 15 to 30 seconds
    """
    if cadence_stage == "warmup":
        return round(random.uniform(240, 500), 1)
    elif cadence_stage == "test":
        return round(random.uniform(15, 30), 1)
    else:  # stable
        return round(random.uniform(90, 240), 1)


class PermanentSuppressionStore:
    """
    Maintains suppression lists for bounced emails and opt-outs.
    Never sends to any address or domain on this list.
    """
    def __init__(self, suppression_file: str = "suppression_list.txt"):
        self.suppression_file = suppression_file
        self.suppressed_emails: Set[str] = set()
        self.suppressed_domains: Set[str] = set()
        self._load()

    def _load(self):
        import os
        if os.path.exists(self.suppression_file):
            try:
                with open(self.suppression_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip().lower()
                        if line:
                            if "@" in line:
                                self.suppressed_emails.add(line)
                            else:
                                self.suppressed_domains.add(line)
            except Exception:
                pass

    def add(self, email_or_domain: str, reason: str = "opt_out"):
        item = email_or_domain.strip().lower()
        if not item:
            return
        if "@" in item:
            self.suppressed_emails.add(item)
        else:
            self.suppressed_domains.add(item)

        try:
            with open(self.suppression_file, "a", encoding="utf-8") as f:
                f.write(f"{item} # {reason}\n")
        except Exception:
            pass

    def is_suppressed(self, email: str) -> bool:
        e = email.strip().lower()
        if e in self.suppressed_emails:
            return True
        domain = e.split("@")[-1] if "@" in e else ""
        if domain and domain in self.suppressed_domains:
            return True
        return False
