"""FastAPI route handlers for PII detection and masking."""

import logging
import time
import uuid
from typing import Any, Dict

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, status
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.responses import Response

from app import __version__
from app.config import get_settings
from app.middleware.rate_limit import limiter
from app.models.requests import (
    AnalyzeRequest,
    AnalyzeResponse,
    AnonymizeBatchRequest,
    AnonymizeBatchResponse,
    AnonymizeRequest,
    AnonymizeResponse,
    BatchAnonymizeResult,
    HealthResponse,
)
from app.services.presidio_service import get_presidio_service

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter()

# Prometheus metrics
REQUEST_COUNT = Counter(
    "pii_api_requests_total",
    "Total API requests",
    ["method", "endpoint", "status"],
)
REQUEST_LATENCY = Histogram(
    "pii_api_request_duration_seconds",
    "Request latency in seconds",
    ["endpoint"],
)

# In-memory store for async large-text tasks
_async_tasks: Dict[str, Dict[str, Any]] = {}


def _record_metrics(endpoint: str, status_code: int, duration_s: float) -> None:
    """Record Prometheus metrics for a completed request."""
    if not settings.prometheus_enabled:
        return
    REQUEST_COUNT.labels(method="POST", endpoint=endpoint, status=status_code).inc()
    REQUEST_LATENCY.labels(endpoint=endpoint).observe(duration_s)


@router.get(
    "/health",
    response_model=HealthResponse,
    tags=["Health"],
    summary="Service health check",
    description="Returns service status, spaCy model load state, and supported entity types.",
)
async def health_check() -> HealthResponse:
    """Verify service and Presidio engine health."""
    service = get_presidio_service()
    health = service.health_check()

    return HealthResponse(
        status="healthy" if health["spacy_model_loaded"] else "degraded",
        version=__version__,
        spacy_model_loaded=health["spacy_model_loaded"],
        spacy_model_name=health["spacy_model_name"],
        supported_entity_types=health["supported_entity_types"],
        cache_enabled=settings.cache_enabled,
        rate_limit_enabled=settings.rate_limit_enabled,
    )


@router.get(
    "/metrics",
    tags=["Monitoring"],
    summary="Prometheus metrics",
    include_in_schema=settings.prometheus_enabled,
)
async def metrics() -> Response:
    """Expose Prometheus metrics for monitoring."""
    if not settings.prometheus_enabled:
        raise HTTPException(status_code=404, detail="Metrics endpoint is disabled")
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@router.post(
    "/analyze",
    response_model=AnalyzeResponse,
    tags=["PII Detection"],
    summary="Detect PII entities in text",
    description="Analyzes input text and returns all detected PII entities with positions and scores.",
)
@limiter.limit(settings.rate_limit)
async def analyze_text(request: Request, body: AnalyzeRequest) -> AnalyzeResponse:
    """Detect PII entities without anonymizing."""
    endpoint = "/analyze"
    start = time.perf_counter()

    try:
        service = get_presidio_service()
        entities, elapsed_ms = service.analyze(body.text)
        _record_metrics(endpoint, 200, time.perf_counter() - start)

        return AnalyzeResponse(
            text=body.text,
            detected_entities=entities,
            entity_count=len(entities),
            processing_time_ms=round(elapsed_ms, 2),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Analyze endpoint failed")
        _record_metrics(endpoint, 500, time.perf_counter() - start)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal error during PII analysis.",
        ) from exc


@router.post(
    "/anonymize",
    response_model=AnonymizeResponse,
    tags=["PII Masking"],
    summary="Anonymize PII in text",
    description="Detects PII and replaces each entity with a type placeholder (e.g. <PERSON>).",
)
@limiter.limit(settings.rate_limit)
async def anonymize_text(
    request: Request,
    body: AnonymizeRequest,
    background_tasks: BackgroundTasks,
) -> AnonymizeResponse:
    """Anonymize text, optionally queueing very large inputs as background tasks."""
    endpoint = "/anonymize"
    start = time.perf_counter()

    # Optional async path for large texts (returns task id via query param)
    if (
        len(body.text) > settings.large_text_threshold
        and request.query_params.get("async") == "true"
    ):
        task_id = str(uuid.uuid4())
        _async_tasks[task_id] = {"status": "pending", "result": None}

        def _process() -> None:
            try:
                service = get_presidio_service()
                anonymized, entities, elapsed = service.anonymize(body.text)
                _async_tasks[task_id] = {
                    "status": "completed",
                    "result": {
                        "original_text": body.text,
                        "anonymized_text": anonymized,
                        "detected_entities": [e.model_dump() for e in entities],
                        "processing_time_ms": round(elapsed, 2),
                    },
                }
            except Exception as exc:
                _async_tasks[task_id] = {"status": "failed", "error": str(exc)}

        background_tasks.add_task(_process)
        raise HTTPException(
            status_code=status.HTTP_202_ACCEPTED,
            detail={"task_id": task_id, "status": "pending", "poll": f"/tasks/{task_id}"},
        )

    try:
        service = get_presidio_service()
        anonymized, entities, elapsed_ms = service.anonymize(body.text)
        _record_metrics(endpoint, 200, time.perf_counter() - start)

        return AnonymizeResponse(
            original_text=body.text,
            anonymized_text=anonymized,
            detected_entities=entities,
            processing_time_ms=round(elapsed_ms, 2),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Anonymize endpoint failed")
        _record_metrics(endpoint, 500, time.perf_counter() - start)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal error during PII anonymization.",
        ) from exc


@router.get("/tasks/{task_id}", tags=["PII Masking"], summary="Poll async anonymization task")
async def get_task_status(task_id: str) -> Dict[str, Any]:
    """Return status and result of a background anonymization task."""
    if task_id not in _async_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"task_id": task_id, **_async_tasks[task_id]}


@router.post(
    "/anonymize/batch",
    response_model=AnonymizeBatchResponse,
    tags=["PII Masking"],
    summary="Batch anonymize multiple texts",
    description="Processes up to 50 texts and returns anonymization results for each.",
)
@limiter.limit(settings.rate_limit)
async def anonymize_batch(request: Request, body: AnonymizeBatchRequest) -> AnonymizeBatchResponse:
    """Anonymize multiple texts in a single request."""
    endpoint = "/anonymize/batch"
    start = time.perf_counter()

    try:
        service = get_presidio_service()
        batch_results = service.anonymize_batch(body.texts)

        results = [
            BatchAnonymizeResult(
                original_text=original,
                anonymized_text=anonymized,
                detected_entities=entities,
                processing_time_ms=round(elapsed, 2),
            )
            for original, anonymized, entities, elapsed in batch_results
        ]

        total_ms = (time.perf_counter() - start) * 1000
        _record_metrics(endpoint, 200, time.perf_counter() - start)

        return AnonymizeBatchResponse(
            results=results,
            total_count=len(results),
            processing_time_ms=round(total_ms, 2),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Batch anonymize endpoint failed")
        _record_metrics(endpoint, 500, time.perf_counter() - start)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal error during batch anonymization.",
        ) from exc
