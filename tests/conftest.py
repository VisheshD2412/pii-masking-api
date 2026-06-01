"""Pytest fixtures and shared test data."""

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

# Realistic Indian + US PII test samples (synthetic / fictional)
SAMPLE_TEXT_FULL = (
    "My name is Rajesh Kumar, my Aadhaar is 1234 5678 9012, "
    "PAN is ABCDE1234F, email rajesh@example.com, phone +91-9876543210."
)

SAMPLE_TEXT_AADHAAR = "UID: 9876 5432 1098 issued by UIDAI."

SAMPLE_TEXT_PAN = "Income tax PAN card number FGHIJ5678K for filing."

SAMPLE_TEXT_EMAIL = "Contact support at help@company.co.in for assistance."

SAMPLE_TEXT_US = "John Smith SSN 123-45-6789 card 4111-1111-1111-1111."

SAMPLE_TEXTS_BATCH = [
    "Priya Sharma email priya.sharma@test.in",
    "Aadhaar 1111 2222 3333 for verification",
    "No PII in this sentence only.",
]


@pytest.fixture(scope="session")
def app():
    """Create FastAPI app once per test session."""
    return create_app()


@pytest.fixture(scope="session")
def client(app):
    """HTTP test client bound to the application."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def presidio_service():
    """Return warmed Presidio service singleton."""
    from app.services.presidio_service import get_presidio_service

    return get_presidio_service()
