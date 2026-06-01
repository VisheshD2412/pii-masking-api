"""Custom Presidio recognizers for Indian PII identifiers."""

import logging
from typing import List

from presidio_analyzer import Pattern, PatternRecognizer

logger = logging.getLogger(__name__)


def build_indian_aadhaar_recognizer() -> PatternRecognizer:
    """
    Recognize Indian Aadhaar numbers (12 digits).

    Supports formats:
    - 123456789012
    - 1234 5678 9012
    - 1234-5678-9012
    """
    patterns = [
        Pattern(
            name="aadhaar_spaced",
            regex=r"\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b",
            score=0.95,
        ),
        Pattern(
            name="aadhaar_continuous",
            regex=r"\b(?<!\d)\d{12}(?!\d)\b",
            score=0.9,
        ),
    ]
    return PatternRecognizer(
        supported_entity="IN_AADHAAR",
        patterns=patterns,
        context=["aadhaar", "aadhar", "uid", "uidai", "unique identification"],
        supported_language="en",
    )


def build_indian_pan_recognizer() -> PatternRecognizer:
    """
    Recognize Indian PAN card numbers.

    Format: 5 uppercase letters + 4 digits + 1 uppercase letter (e.g. ABCDE1234F).
    """
    patterns = [
        Pattern(
            name="pan_standard",
            regex=r"\b[A-Z]{5}[0-9]{4}[A-Z]{1}\b",
            score=0.95,
        ),
        Pattern(
            name="pan_lowercase",
            regex=r"\b[a-zA-Z]{5}[0-9]{4}[a-zA-Z]{1}\b",
            score=0.85,
        ),
    ]
    return PatternRecognizer(
        supported_entity="IN_PAN",
        patterns=patterns,
        context=["pan", "permanent account", "income tax", "tax id"],
        supported_language="en",
    )


def build_indian_voter_id_recognizer() -> PatternRecognizer:
    """
    Recognize Indian Voter ID (EPIC) numbers.

    Typically 10 alphanumeric characters; common formats vary by state.
    """
    patterns = [
        Pattern(
            name="voter_id_alphanumeric",
            regex=r"\b[A-Z]{3}[0-9]{7}\b",
            score=0.9,
        ),
        Pattern(
            name="voter_id_mixed",
            regex=r"\b[A-Z0-9]{10}\b",
            score=0.75,
        ),
    ]
    return PatternRecognizer(
        supported_entity="IN_VOTER_ID",
        patterns=patterns,
        context=["voter", "epic", "elector", "election", "voter id"],
        supported_language="en",
    )


def build_indian_driving_license_recognizer() -> PatternRecognizer:
    """
    Recognize Indian driving license numbers (basic multi-state patterns).

    Common patterns include state code + year + serial (e.g. DL-01-2015-1234567).
    """
    patterns = [
        Pattern(
            name="dl_standard_hyphen",
            regex=r"\b[A-Z]{2}[\-\s]?\d{2}[\-\s]?\d{4}[\-\s]?\d{7}\b",
            score=0.9,
        ),
        Pattern(
            name="dl_compact",
            regex=r"\b[A-Z]{2}\d{13}\b",
            score=0.85,
        ),
        Pattern(
            name="dl_state_year_serial",
            regex=r"\bDL[\-\s]?[0-9]{2}[\-\s]?[0-9]{4}[\-\s]?[0-9]{7}\b",
            score=0.88,
        ),
    ]
    return PatternRecognizer(
        supported_entity="IN_DRIVER_LICENSE",
        patterns=patterns,
        context=["driving", "license", "licence", "dl no", "rto", "transport"],
        supported_language="en",
    )


def get_custom_recognizers() -> List[PatternRecognizer]:
    """Return all custom Indian PII recognizers for registration with Presidio."""
    recognizers = [
        build_indian_aadhaar_recognizer(),
        build_indian_pan_recognizer(),
        build_indian_voter_id_recognizer(),
        build_indian_driving_license_recognizer(),
    ]
    logger.info(
        "Loaded %d custom Indian PII recognizers: %s",
        len(recognizers),
        [r.supported_entities for r in recognizers],
    )
    return recognizers
