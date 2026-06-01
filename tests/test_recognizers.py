"""Unit tests for custom Indian PII recognizers."""

import pytest
from presidio_analyzer import AnalyzerEngine

from app.services.custom_recognizers import get_custom_recognizers


@pytest.fixture(scope="module")
def analyzer_with_custom():
    """Analyzer engine with only custom recognizers registered."""
    engine = AnalyzerEngine()
    for recognizer in get_custom_recognizers():
        engine.registry.add_recognizer(recognizer)
    return engine


class TestIndianAadhaarRecognizer:
    """Tests for IN_AADHAAR pattern recognition."""

    def test_spaced_aadhaar(self, analyzer_with_custom):
        text = "Aadhaar number is 1234 5678 9012 for KYC."
        results = analyzer_with_custom.analyze(
            text=text, language="en", entities=["IN_AADHAAR"]
        )
        assert len(results) >= 1
        assert results[0].entity_type == "IN_AADHAAR"
        assert "1234" in text[results[0].start : results[0].end]

    def test_continuous_aadhaar(self, analyzer_with_custom):
        text = "UID 987654321098 verified."
        results = analyzer_with_custom.analyze(
            text=text, language="en", entities=["IN_AADHAAR"]
        )
        assert len(results) >= 1


class TestIndianPanRecognizer:
    """Tests for IN_PAN pattern recognition."""

    def test_standard_pan(self, analyzer_with_custom):
        text = "PAN ABCDE1234F is required."
        results = analyzer_with_custom.analyze(
            text=text, language="en", entities=["IN_PAN"]
        )
        assert len(results) >= 1
        assert text[results[0].start : results[0].end] == "ABCDE1234F"


class TestIndianVoterIdRecognizer:
    """Tests for IN_VOTER_ID pattern recognition."""

    def test_voter_id_pattern(self, analyzer_with_custom):
        text = "EPIC voter id ABC1234567 registered."
        results = analyzer_with_custom.analyze(
            text=text, language="en", entities=["IN_VOTER_ID"]
        )
        assert len(results) >= 1


class TestIndianDrivingLicenseRecognizer:
    """Tests for IN_DRIVER_LICENSE pattern recognition."""

    def test_dl_pattern(self, analyzer_with_custom):
        text = "Driving license DL-01-2015-1234567 issued."
        results = analyzer_with_custom.analyze(
            text=text, language="en", entities=["IN_DRIVER_LICENSE"]
        )
        assert len(results) >= 1
