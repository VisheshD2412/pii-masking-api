# PII Masking API

Production-ready **PII detection and masking** service built with **Microsoft Presidio**, **FastAPI**, and **spaCy**, designed for deployment on **Azure App Service**.

## Why this matters

Enterprises processing customer data must detect and redact personally identifiable information (PII) before logging, analytics, or LLM pipelines. This API provides:

- **Deterministic, on-premise-friendly** PII detection (no external API calls required)
- **US + Indian identifier** support including custom Aadhaar, PAN, Voter ID, and Driving License recognizers
- **REST API** suitable for microservice integration, batch jobs, and compliance workflows
- **Azure-ready** container deployment with health checks, metrics, and rate limiting

## Technology stack

| Component | Purpose |
|-----------|---------|
| FastAPI | Async REST API framework |
| Microsoft Presidio | Analyzer + Anonymizer engines |
| spaCy `en_core_web_sm` | NLP backbone for NER |
| Pydantic | Request/response validation |
| Uvicorn | ASGI server |
| slowapi | Rate limiting |
| Prometheus | `/metrics` endpoint |
| Locust | Load testing |
| Streamlit | Optional interactive UI |

## Project structure

```
pii-masking-api/
├── app/
│   ├── main.py                 # FastAPI app factory
│   ├── config.py               # Environment-based settings
│   ├── api/routes.py           # Endpoints
│   ├── services/
│   │   ├── presidio_service.py # Singleton Presidio wrapper
│   │   └── custom_recognizers.py
│   ├── middleware/             # Logging + rate limit
│   └── utils/cache.py          # LRU analysis cache
├── tests/
├── load_tests/locustfile.py
├── ui/streamlit_app.py
├── Dockerfile
├── docker-compose.yml
├── startup.sh
└── azure-deploy.json
```

## Quick start (local)

### Prerequisites

- Python 3.11+
- pip

### Setup

```bash
cd pii-masking-api
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

### Run API

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Open Swagger UI: http://localhost:8000/docs

### Run tests

```bash
pytest -v
```

### Run Streamlit UI (optional)

```bash
streamlit run ui/streamlit_app.py
```

## Docker

```bash
docker compose build
docker compose up -d
curl http://localhost:8000/health
```

With UI profile:

```bash
docker compose --profile ui up -d
```

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Service health + entity types |
| POST | `/analyze` | Detect PII entities |
| POST | `/anonymize` | Mask PII with placeholders |
| POST | `/anonymize/batch` | Batch anonymization (max 50) |
| GET | `/metrics` | Prometheus metrics |
| GET | `/docs` | OpenAPI Swagger |

### Supported entity types

`PERSON`, `EMAIL_ADDRESS`, `PHONE_NUMBER`, `US_SSN`, `CREDIT_CARD`, `LOCATION`, `DATE_TIME`, `US_DRIVER_LICENSE`, `US_BANK_NUMBER`, `IN_AADHAAR`, `IN_PAN`, `IN_VOTER_ID`, `IN_DRIVER_LICENSE`

### Sample response (`POST /anonymize`)

**Request:**

```json
{
  "text": "My name is Rajesh Kumar, my Aadhaar is 1234 5678 9012, and my email is rajesh@example.com"
}
```

**Response:**

```json
{
  "original_text": "My name is Rajesh Kumar, my Aadhaar is 1234 5678 9012, and my email is rajesh@example.com",
  "anonymized_text": "My name is <PERSON>, my Aadhaar is <IN_AADHAAR>, and my email is <EMAIL_ADDRESS>",
  "detected_entities": [
    {"type": "PERSON", "text": "Rajesh Kumar", "start": 11, "end": 23, "score": 0.85},
    {"type": "IN_AADHAAR", "text": "1234 5678 9012", "start": 36, "end": 51, "score": 0.95},
    {"type": "EMAIL_ADDRESS", "text": "rajesh@example.com", "start": 66, "end": 84, "score": 0.98}
  ],
  "processing_time_ms": 45.2
}
```

> Scores and exact spans may vary slightly based on spaCy/Presidio versions.

## Custom Indian PII recognizers

Registered in `app/services/custom_recognizers.py`:

| Entity | Pattern | Example |
|--------|---------|---------|
| `IN_AADHAAR` | 12 digits, spaced/hyphenated | `1234 5678 9012` |
| `IN_PAN` | 5 letters + 4 digits + 1 letter | `ABCDE1234F` |
| `IN_VOTER_ID` | 10 alphanumeric (EPIC-style) | `ABC1234567` |
| `IN_DRIVER_LICENSE` | State/year/serial variants | `DL-01-2015-1234567` |

Context words (e.g. "aadhaar", "pan", "voter") boost confidence when present.

## Load testing

Start API, then:

```bash
locust -f load_tests/locustfile.py --host=http://localhost:8000
```

Headless (100 concurrent users):

```bash
locust -f load_tests/locustfile.py --host=http://localhost:8000 \
  --users 100 --spawn-rate 10 --run-time 60s --headless
```

### Sample load test results

Run on Apple M-series / 8GB RAM, local Docker, single worker:

| Metric | Typical value |
|--------|----------------|
| Requests/sec | 15–40 rps |
| p50 latency | 80–150 ms |
| p95 latency | 200–400 ms |
| Failure rate | < 1% |

> Presidio + spaCy are CPU-bound; scale horizontally on Azure with multiple instances.

## Azure deployment

### Option A: Azure CLI + Container Registry

```bash
# Variables
RESOURCE_GROUP="rg-pii-masking"
LOCATION="eastus"
ACR_NAME="piimaskingacr"          # must be globally unique
APP_NAME="pii-masking-api-prod"   # must be globally unique
IMAGE="pii-masking-api:latest"

# Login
az login
az group create --name $RESOURCE_GROUP --location $LOCATION

# Create ACR and build image
az acr create --resource-group $RESOURCE_GROUP --name $ACR_NAME --sku Basic --admin-enabled true
az acr login --name $ACR_NAME
az acr build --registry $ACR_NAME --image $IMAGE .

# Deploy ARM template
ACR_LOGIN=$(az acr show --name $ACR_NAME --query loginServer -o tsv)
ACR_USER=$(az acr credential show --name $ACR_NAME --query username -o tsv)
ACR_PASS=$(az acr credential show --name $ACR_NAME --query passwords[0].value -o tsv)

az deployment group create \
  --resource-group $RESOURCE_GROUP \
  --template-file azure-deploy.json \
  --parameters \
    webAppName=$APP_NAME \
    location=$LOCATION \
    linuxFxVersion="DOCKER|${ACR_LOGIN}/${IMAGE}" \
    dockerRegistryUrl="https://${ACR_LOGIN}" \
    dockerRegistryUsername=$ACR_USER \
    dockerRegistryPassword=$ACR_PASS

# Configure container on App Service
az webapp config container set \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --docker-custom-image-name "${ACR_LOGIN}/${IMAGE}" \
  --docker-registry-server-url "https://${ACR_LOGIN}" \
  --docker-registry-server-user $ACR_USER \
  --docker-registry-server-password $ACR_PASS

az webapp restart --name $APP_NAME --resource-group $RESOURCE_GROUP
echo "https://${APP_NAME}.azurewebsites.net/health"
```

### Option B: App Service from Docker Hub

Push image to a registry, set `linuxFxVersion` to `DOCKER|<image>` in the ARM template.

## Environment variables

See `.env.example` for all options. Key settings:

| Variable | Default | Description |
|----------|---------|-------------|
| `MAX_TEXT_LENGTH` | 5000 | Max input characters |
| `RATE_LIMIT` | 60/minute | slowapi limit |
| `CACHE_ENABLED` | true | LRU analysis cache |
| `SCORE_THRESHOLD` | 0.35 | Min entity confidence |

## curl examples

### Local (`http://localhost:8000`)

```bash
# Health
curl -s http://localhost:8000/health | jq

# Analyze
curl -s -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"text": "Rajesh Kumar, Aadhaar 1234 5678 9012, rajesh@example.com"}' | jq

# Anonymize
curl -s -X POST http://localhost:8000/anonymize \
  -H "Content-Type: application/json" \
  -d '{"text": "My name is Rajesh Kumar, my Aadhaar is 1234 5678 9012, and my email is rajesh@example.com"}' | jq

# Batch
curl -s -X POST http://localhost:8000/anonymize/batch \
  -H "Content-Type: application/json" \
  -d '{"texts": ["Priya Sharma priya@test.in", "PAN ABCDE1234F"]}' | jq

# Metrics
curl -s http://localhost:8000/metrics | head -20
```

### Docker local

Same commands against `http://localhost:8000` after `docker compose up`.

### Azure (replace hostname)

```bash
AZURE_URL="https://pii-masking-api-prod.azurewebsites.net"

curl -s "${AZURE_URL}/health" | jq

curl -s -X POST "${AZURE_URL}/anonymize" \
  -H "Content-Type: application/json" \
  -d '{"text": "Contact Amit Patel at amit@company.in, Aadhaar 9876 5432 1098"}' | jq
```

## License

MIT — use freely for portfolio and interview demonstrations.
