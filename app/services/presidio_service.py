"""Singleton Presidio analyzer and anonymizer service."""

import logging
import time
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple

from presidio_analyzer import AnalyzerEngine, RecognizerResult
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

from app.config import Settings, get_settings
from app.models.requests import DetectedEntity
from app.services.custom_recognizers import get_custom_recognizers
from app.utils.cache import analysis_cache

logger = logging.getLogger(__name__)


class PresidioService:
    """
    Thread-safe singleton wrapping Presidio AnalyzerEngine and AnonymizerEngine.

    Loads spaCy NLP model once and registers custom Indian PII recognizers.
    """

    _instance: Optional["PresidioService"] = None
    _lock: Lock = Lock()

    def __new__(cls, settings: Optional[Settings] = None) -> "PresidioService":
        """Ensure only one PresidioService instance exists."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, settings: Optional[Settings] = None) -> None:
        """Initialize analyzer and anonymizer engines (once)."""
        if getattr(self, "_initialized", False):
            return

        self.settings = settings or get_settings()
        self._spacy_loaded = False
        self._analyzer: Optional[AnalyzerEngine] = None
        self._anonymizer: Optional[AnonymizerEngine] = None

        self._initialize_engines()
        self._initialized = True

    def _initialize_engines(self) -> None:
        """Create Presidio engines and register custom recognizers."""
        logger.info("Initializing Presidio engines with spaCy model: %s", self.settings.spacy_model)

        try:
            self._analyzer = AnalyzerEngine()
            registry = self._analyzer.registry

            for recognizer in get_custom_recognizers():
                registry.add_recognizer(recognizer)
                logger.debug("Registered recognizer: %s", recognizer.supported_entities)

            # Verify spaCy model is available (direct load is reliable across Presidio versions)
            try:
                import spacy

                spacy.load(self.settings.spacy_model)
                self._spacy_loaded = True
                logger.info("spaCy model loaded: %s", self.settings.spacy_model)
            except OSError as spacy_exc:
                logger.warning("spaCy model not loaded: %s", spacy_exc)

            self._anonymizer = AnonymizerEngine()
            logger.info("Presidio engines initialized successfully")

        except Exception as exc:
            logger.exception("Failed to initialize Presidio engines")
            raise RuntimeError(f"Presidio initialization failed: {exc}") from exc

    @property
    def spacy_model_loaded(self) -> bool:
        """Return whether the spaCy NLP model is available."""
        return self._spacy_loaded

    @property
    def supported_entities(self) -> List[str]:
        """Return configured supported entity types."""
        return list(self.settings.supported_entities)

    def analyze(
        self,
        text: str,
        use_cache: bool = True,
    ) -> Tuple[List[DetectedEntity], float]:
        """
        Analyze text for PII entities.

        Returns detected entities and processing time in milliseconds.
        """
        if self._analyzer is None:
            raise RuntimeError("Analyzer engine is not initialized")

        start = time.perf_counter()

        if use_cache and self.settings.cache_enabled:
            cached = analysis_cache.get(text)
            if cached is not None:
                elapsed_ms = (time.perf_counter() - start) * 1000
                return cached, elapsed_ms

        results: List[RecognizerResult] = self._analyzer.analyze(
            text=text,
            language=self.settings.default_language,
            entities=self.settings.supported_entities,
            score_threshold=self.settings.score_threshold,
        )

        entities = self._convert_results(text, results)

        if use_cache and self.settings.cache_enabled:
            analysis_cache.set(text, entities)

        elapsed_ms = (time.perf_counter() - start) * 1000
        return entities, elapsed_ms

    def anonymize(self, text: str, use_cache: bool = True) -> Tuple[str, List[DetectedEntity], float]:
        """
        Anonymize text by replacing PII with entity-type placeholders.

        Returns anonymized text, detected entities, and processing time in ms.
        """
        if self._analyzer is None or self._anonymizer is None:
            raise RuntimeError("Presidio engines are not initialized")

        start = time.perf_counter()

        entities, _ = self.analyze(text, use_cache=use_cache)

        if not entities:
            elapsed_ms = (time.perf_counter() - start) * 1000
            return text, [], elapsed_ms

        recognizer_results = [
            RecognizerResult(
                entity_type=e.type,
                start=e.start,
                end=e.end,
                score=e.score,
            )
            for e in entities
        ]

        operators: Dict[str, OperatorConfig] = {
            entity_type: OperatorConfig("replace", {"new_value": f"<{entity_type}>"})
            for entity_type in self.settings.supported_entities
        }

        anonymized_result = self._anonymizer.anonymize(
            text=text,
            analyzer_results=recognizer_results,
            operators=operators,
        )

        elapsed_ms = (time.perf_counter() - start) * 1000
        return anonymized_result.text, entities, elapsed_ms

    def anonymize_batch(
        self,
        texts: List[str],
        use_cache: bool = True,
    ) -> List[Tuple[str, str, List[DetectedEntity], float]]:
        """
        Anonymize multiple texts sequentially.

        Returns list of (original, anonymized, entities, processing_time_ms).
        """
        results: List[Tuple[str, str, List[DetectedEntity], float]] = []
        for text in texts:
            anonymized, entities, elapsed = self.anonymize(text, use_cache=use_cache)
            results.append((text, anonymized, entities, elapsed))
        return results

    def _convert_results(
        self,
        text: str,
        results: List[RecognizerResult],
    ) -> List[DetectedEntity]:
        """Convert Presidio RecognizerResult objects to API DetectedEntity models."""
        # Sort by start position and deduplicate overlapping spans (keep higher score)
        sorted_results = sorted(results, key=lambda r: (r.start, -(r.end - r.start)))

        entities: List[DetectedEntity] = []
        last_end = -1

        for result in sorted_results:
            if result.start < last_end:
                continue

            entity = DetectedEntity(
                type=result.entity_type,
                text=text[result.start : result.end],
                start=result.start,
                end=result.end,
                score=round(float(result.score), 4),
            )
            entities.append(entity)
            last_end = result.end

        return entities

    def health_check(self) -> Dict[str, Any]:
        """Return health metadata for the service."""
        return {
            "spacy_model_loaded": self._spacy_loaded,
            "spacy_model_name": self.settings.spacy_model,
            "supported_entity_types": self.supported_entities,
        }


def get_presidio_service() -> PresidioService:
    """Return the global PresidioService singleton."""
    return PresidioService()
