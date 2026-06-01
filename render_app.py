"""
Minimal PII Masking API for Render free tier
Uses small spaCy model to stay under 512MB memory limit
"""

from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import time
import os

# Suppress spammy logs
os.environ["PRESIDIO_LOGGING_LEVEL"] = "ERROR"

from presidio_analyzer import AnalyzerEngine
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_anonymizer import AnonymizerEngine

print("Loading small spaCy model (en_core_web_sm)...")

# Force small spaCy model (40MB instead of 400MB)
nlp_config = {
    "nlp_engine_name": "spacy",
    "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}]
}
provider = NlpEngineProvider(nlp_config=nlp_config)
nlp_engine = provider.create_engine()

analyzer = AnalyzerEngine(nlp_engine=nlp_engine)
anonymizer = AnonymizerEngine()
print("✅ Models loaded successfully!")

app = FastAPI(title="PII Masking API", version="1.0.0")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TextRequest(BaseModel):
    text: str

@app.get("/")
async def root():
    return {"message": "PII Masking API - Enterprise data security"}

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "PII Masking API", "model": "en_core_web_sm"}

@app.post("/analyze")
async def analyze(request: TextRequest):
    results = analyzer.analyze(text=request.text, language="en")
    return {
        "text": request.text,
        "entities": [
            {
                "type": r.entity_type,
                "start": r.start,
                "end": r.end,
                "score": round(r.score, 2)
            }
            for r in results
        ]
    }

@app.post("/anonymize")
async def anonymize(request: TextRequest):
    start_time = time.time()
    
    results = analyzer.analyze(text=request.text, language="en")
    anonymized_result = anonymizer.anonymize(text=request.text, analyzer_results=results)
    
    processing_time = (time.time() - start_time) * 1000
    
    return {
        "original": request.text,
        "anonymized": anonymized_result.text,
        "entities_found": len(results),
        "processing_time_ms": round(processing_time, 2)
    }

