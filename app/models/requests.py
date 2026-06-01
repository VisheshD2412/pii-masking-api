"""Pydantic models for API request and response validation."""

from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from app.config import get_settings


class TextRequestMixin(BaseModel):
    """Shared text field with length validation."""

    text: str = Field(
        ...,
        min_length=1,
        description="Input text to analyze or anonymize.",
        examples=["My name is Rajesh Kumar and my email is rajesh@example.com"],
    )

    @field_validator("text")
    @classmethod
    def validate_text_length(cls, value: str) -> str:
        """Reject text exceeding configured maximum length."""
        max_len = get_settings().max_text_length
        if len(value) > max_len:
            raise ValueError(f"Text exceeds maximum length of {max_len} characters.")
        return value.strip()


class AnalyzeRequest(TextRequestMixin):
    """Request body for POST /analyze."""


class AnonymizeRequest(TextRequestMixin):
    """Request body for POST /anonymize."""


class AnonymizeBatchRequest(BaseModel):
    """Request body for POST /anonymize/batch."""

    texts: List[str] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="List of texts to anonymize (max 50 per batch).",
    )

    @field_validator("texts")
    @classmethod
    def validate_texts(cls, values: List[str]) -> List[str]:
        """Validate each text in the batch."""
        max_len = get_settings().max_text_length
        cleaned: List[str] = []
        for idx, text in enumerate(values):
            stripped = text.strip()
            if not stripped:
                raise ValueError(f"Text at index {idx} is empty.")
            if len(stripped) > max_len:
                raise ValueError(
                    f"Text at index {idx} exceeds maximum length of {max_len} characters."
                )
            cleaned.append(stripped)
        return cleaned


class DetectedEntity(BaseModel):
    """A single detected PII entity."""

    type: str = Field(..., description="Entity type label (e.g. PERSON, IN_AADHAAR).")
    text: str = Field(..., description="Matched substring from the input.")
    start: int = Field(..., ge=0, description="Start character offset (inclusive).")
    end: int = Field(..., ge=0, description="End character offset (exclusive).")
    score: float = Field(..., ge=0.0, le=1.0, description="Confidence score.")


class AnalyzeResponse(BaseModel):
    """Response for POST /analyze."""

    text: str
    detected_entities: List[DetectedEntity]
    entity_count: int
    processing_time_ms: float


class AnonymizeResponse(BaseModel):
    """Response for POST /anonymize."""

    original_text: str
    anonymized_text: str
    detected_entities: List[DetectedEntity]
    processing_time_ms: float


class BatchAnonymizeResult(BaseModel):
    """Single item in a batch anonymization response."""

    original_text: str
    anonymized_text: str
    detected_entities: List[DetectedEntity]
    processing_time_ms: float


class AnonymizeBatchResponse(BaseModel):
    """Response for POST /anonymize/batch."""

    results: List[BatchAnonymizeResult]
    total_count: int
    processing_time_ms: float


class HealthResponse(BaseModel):
    """Response for GET /health."""

    status: str
    version: str
    spacy_model_loaded: bool
    spacy_model_name: str
    supported_entity_types: List[str]
    cache_enabled: bool
    rate_limit_enabled: bool


class ErrorResponse(BaseModel):
    """Standard error response body."""

    detail: str
    error_code: Optional[str] = None


class AsyncAnonymizeResponse(BaseModel):
    """Response when large text is queued for background processing."""

    task_id: str
    status: str
    message: str
