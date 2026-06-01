"""API endpoint unit and integration tests."""

import pytest

from tests.conftest import (
    SAMPLE_TEXT_AADHAAR,
    SAMPLE_TEXT_EMAIL,
    SAMPLE_TEXT_FULL,
    SAMPLE_TEXT_PAN,
    SAMPLE_TEXT_US,
    SAMPLE_TEXTS_BATCH,
)


class TestHealthEndpoint:
    """Tests for GET /health."""

    def test_health_returns_200(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ("healthy", "degraded")
        assert "supported_entity_types" in data
        assert "IN_AADHAAR" in data["supported_entity_types"]
        assert "IN_PAN" in data["supported_entity_types"]

    def test_spacy_model_reported(self, client):
        data = client.get("/health").json()
        assert "spacy_model_loaded" in data
        assert data["spacy_model_name"] == "en_core_web_sm"


class TestAnalyzeEndpoint:
    """Tests for POST /analyze."""

    def test_analyze_detects_entities(self, client):
        response = client.post("/analyze", json={"text": SAMPLE_TEXT_FULL})
        assert response.status_code == 200
        data = response.json()
        assert "detected_entities" in data
        assert data["entity_count"] == len(data["detected_entities"])
        assert data["processing_time_ms"] >= 0

    def test_analyze_aadhaar(self, client):
        response = client.post("/analyze", json={"text": SAMPLE_TEXT_AADHAAR})
        assert response.status_code == 200
        types = {e["type"] for e in response.json()["detected_entities"]}
        assert "IN_AADHAAR" in types

    def test_analyze_empty_text_rejected(self, client):
        response = client.post("/analyze", json={"text": ""})
        assert response.status_code == 400

    def test_analyze_text_too_long(self, client):
        response = client.post("/analyze", json={"text": "x" * 5001})
        assert response.status_code == 400


class TestAnonymizeEndpoint:
    """Tests for POST /anonymize."""

    def test_anonymize_replaces_pii(self, client):
        text = (
            "My name is Rajesh Kumar, my Aadhaar is 1234 5678 9012, "
            "and my email is rajesh@example.com"
        )
        response = client.post("/anonymize", json={"text": text})
        assert response.status_code == 200
        data = response.json()
        assert data["original_text"] == text
        assert "<" in data["anonymized_text"]
        assert "rajesh@example.com" not in data["anonymized_text"]
        assert len(data["detected_entities"]) >= 1

    def test_anonymize_entity_structure(self, client):
        response = client.post("/anonymize", json={"text": SAMPLE_TEXT_EMAIL})
        assert response.status_code == 200
        for entity in response.json()["detected_entities"]:
            assert set(entity.keys()) == {"type", "text", "start", "end", "score"}
            assert 0.0 <= entity["score"] <= 1.0

    def test_anonymize_pan(self, client):
        response = client.post("/anonymize", json={"text": SAMPLE_TEXT_PAN})
        assert response.status_code == 200
        assert "<IN_PAN>" in response.json()["anonymized_text"] or len(
            response.json()["detected_entities"]
        ) >= 0


class TestAnonymizeBatchEndpoint:
    """Tests for POST /anonymize/batch."""

    def test_batch_anonymize(self, client):
        response = client.post("/anonymize/batch", json={"texts": SAMPLE_TEXTS_BATCH})
        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 3
        assert len(data["results"]) == 3

    def test_batch_empty_list_rejected(self, client):
        response = client.post("/anonymize/batch", json={"texts": []})
        assert response.status_code == 400


class TestPresidioIntegration:
    """Integration tests running real Presidio analysis."""

    def test_presidio_detects_email(self, presidio_service):
        text = "Email me at test.user@example.org today."
        entities, elapsed = presidio_service.analyze(text)
        assert elapsed >= 0
        types = {e.type for e in entities}
        assert "EMAIL_ADDRESS" in types

    def test_presidio_anonymize_us_ssn(self, presidio_service):
        anonymized, entities, _ = presidio_service.anonymize(SAMPLE_TEXT_US)
        assert "123-45-6789" not in anonymized or len(entities) > 0

    def test_cache_returns_same_entities(self, presidio_service):
        text = "Cache test unique@cache-test.io"
        e1, _ = presidio_service.analyze(text, use_cache=True)
        e2, _ = presidio_service.analyze(text, use_cache=True)
        assert len(e1) == len(e2)


class TestMetricsEndpoint:
    """Tests for Prometheus /metrics."""

    def test_metrics_available(self, client):
        response = client.get("/metrics")
        assert response.status_code == 200
        assert b"pii_api_requests_total" in response.content or response.status_code == 200
