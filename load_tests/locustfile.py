"""Locust load test for PII Masking API.

Run:
    locust -f load_tests/locustfile.py --host=http://localhost:8000

Headless (100 users, 10/s spawn, 60s):
    locust -f load_tests/locustfile.py --host=http://localhost:8000 \\
        --users 100 --spawn-rate 10 --run-time 60s --headless
"""

import json
import random

from locust import HttpUser, between, task

SAMPLE_TEXTS = [
    "My name is Rajesh Kumar, Aadhaar 1234 5678 9012, email rajesh@example.com",
    "Priya Sharma PAN FGHIJ5678K phone +91-9876543210",
    "Contact john.doe@corp.com SSN 123-45-6789",
    "Voter ID ABC1234567 at polling station",
    "DL-01-2015-1234567 driving license verification",
    "No sensitive data in this plain sentence.",
]


class PIIMaskingUser(HttpUser):
    """Simulates API consumers hitting analyze and anonymize endpoints."""

    wait_time = between(0.5, 2.0)

    def on_start(self) -> None:
        """Verify service is up before load test."""
        self.client.get("/health")

    @task(3)
    def anonymize(self) -> None:
        text = random.choice(SAMPLE_TEXTS)
        with self.client.post(
            "/anonymize",
            json={"text": text},
            catch_response=True,
            name="/anonymize",
        ) as response:
            if response.status_code != 200:
                response.failure(f"Status {response.status_code}: {response.text}")
            else:
                data = response.json()
                if "anonymized_text" not in data:
                    response.failure("Missing anonymized_text in response")

    @task(2)
    def analyze(self) -> None:
        text = random.choice(SAMPLE_TEXTS)
        self.client.post("/analyze", json={"text": text}, name="/analyze")

    @task(1)
    def batch_anonymize(self) -> None:
        texts = random.sample(SAMPLE_TEXTS, k=3)
        self.client.post(
            "/anonymize/batch",
            json={"texts": texts},
            name="/anonymize/batch",
        )

    @task(1)
    def health(self) -> None:
        self.client.get("/health", name="/health")
