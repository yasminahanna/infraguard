# InfraGuard

InfraGuard is a production-oriented AI engineering system for road safety risk analysis. It detects risky driving behavior from camera inputs, identifies emerging hotspot segments, and generates infrastructure recommendations using an LLM-based recommender.

The project is built for the AI Engineering final project and emphasizes distributed service architecture, validation, QA, observability, deployment readiness, and AI lifecycle planning.

## Problem

Cities and road safety teams often rely on delayed crash reports, citizen complaints, or manual inspection to identify dangerous road segments. InfraGuard aims to detect early risk signals from camera evidence and convert them into actionable infrastructure recommendations.

## System Overview

InfraGuard uses one External Endpoint and three Internal Endpoints.

Flow:

    Client / Demo User
      -> EEP Gateway
      -> Detection IEP
      -> Hotspot IEP
      -> Recommender IEP
      -> Final response

## Services

### EEP Gateway

Public API boundary.

Responsibilities:

- API key validation.
- Request validation.
- Payload constraints.
- Orchestration across internal services.
- Timeout and failure handling.
- Unified final response.

Port:

    8000

### Detection IEP

Internal Endpoint 1.

Responsibilities:

- Accept frame batches.
- Detect or estimate reckless-driving events.
- Return structured events with severity and confidence.

Port:

    8001

### Hotspot IEP

Internal Endpoint 2.

Responsibilities:

- Consume detection events.
- Compute hotspot score.
- Estimate trend against baseline.
- Return risk evidence.

Port:

    8002

### Recommender IEP

Internal Endpoint 3.

Responsibilities:

- Consume detection and hotspot evidence.
- Use an LLM to recommend road safety interventions.
- Validate strict JSON output.

Port:

    8003

The Recommender IEP also supports optional web RAG. When enabled, it searches for relevant public road-safety context using the event types, hotspot risk, and location metadata, then includes that retrieved context in the LLM prompt.

## Current Implementation Status

Implemented:

- Four FastAPI services.
- Docker Compose orchestration.
- API key validation.
- Pydantic request validation.
- Detection IEP placeholder logic.
- Hotspot scoring logic.
- OpenAI-based recommender interface.
- Emergency EEP fallback if recommender is unavailable.
- Prometheus-style `/metrics` endpoints.
- Unit/API tests for Detection, Hotspot, and Recommender IEPs.
- Integration tests for EEP orchestration.
- Rubric-aligned documentation.

Planned:

- Real computer vision detection.
- Dataset-backed evaluation.
- Classifier fallback trained on real public traffic or crash data.
- Prometheus and Grafana containers.
- Kubernetes manifests.
- Cloud deployment.
- MLflow or equivalent lifecycle tracking.



## Local Setup

Requirements:

- Docker Desktop
- Python 3.12 or Python 3.11
- PowerShell on Windows

Create environment file:

    copy .env.example .env

Run all services:

    docker compose up --build

Health checks:

    curl.exe http://localhost:8000/health
    curl.exe http://localhost:8001/health
    curl.exe http://localhost:8002/health
    curl.exe http://localhost:8003/health

## Full Local API Test

Run:

    curl.exe -X POST http://localhost:8000/v1/analyze `
      -H "Content-Type: application/json" `
      -H "X-API-Key: dev-secret-key" `
      --data-binary "@samples/analyze_request.json"

Expected:

- `status` is `completed`.
- Detection output is returned.
- Hotspot output is returned.
- Recommendation output is returned.
- If the OpenAI key is missing, the EEP returns an explicit emergency fallback.

## Testing

Detection tests:

    cd services\detection_iep
    pytest

Hotspot tests:

    cd services\hotspot_iep
    pytest

Recommender tests:

    cd services\recommender_iep
    pytest

Integration tests:

    cd C:\Users\yasmi\infraguard
    pytest tests\integration

Deployed E2E test:

    pytest tests\e2e

This test is skipped unless these environment variables are set:

    DEPLOYED_EEP_URL
    DEPLOYED_API_KEY

After cloud deployment, these variables allow the test suite to verify the hosted public EEP endpoint.

Current passing tests:

- Detection IEP: 4 passing.
- Hotspot IEP: 5 passing.
- Recommender IEP: 5 passing.
- EEP integration: 3 passing.

## Documentation

See the `docs` folder:

- `architecture.md`
- `api_contracts.md`
- `tradeoffs.md`
- `qa_strategy.md`
- `dataset_plan.md`
- `security_and_robustness.md`
- `observability.md`
- `deployment.md`
- `cost_estimate.md`
- `mlops_llmops_strategy.md`
- `demo_script.md`

## Environment Variables

Example:

    API_KEY=dev-secret-key
    DETECTION_IEP_URL=http://detection-iep:8001
    HOTSPOT_IEP_URL=http://hotspot-iep:8002
    RECOMMENDER_IEP_URL=http://recommender-iep:8003
    OPENAI_API_KEY=
    LLM_PROVIDER=openai
    LLM_MODEL=gpt-4o-mini
    LLM_TIMEOUT_SECONDS=12
    MAX_FRAMES_PER_REQUEST=8
    MAX_PAYLOAD_MB=10
    REQUEST_TIMEOUT_SECONDS=10

Do not commit `.env`.

## Security Notes

Implemented:

- API key protection.
- Payload validation.
- Frame count limits.
- Controlled recommender failure behavior.

Planned:

- Rate limiting.
- Request body size limits.
- Secret manager integration in cloud.
- Privacy controls for raw images/video.

## Project Direction

InfraGuard is being developed as a production-style AI system, not a notebook demo or thin API wrapper. The final version will include cloud deployment, observability dashboards, Kubernetes manifests, lifecycle tracking, dataset-backed evaluation, and a polished live demo.

## Fine-Tuning Plan

InfraGuard does not fine-tune the recommender model yet.

The planned approach is:

- use RAG for current and location-specific facts,
- use golden evaluation examples to measure recommendation quality,
- fine-tune only after collecting enough high-quality reviewed examples,
- use fine-tuning to improve recommendation style, JSON consistency, evidence use, and uncertainty wording.

Fine-tuning will not replace RAG.

## Admin Dashboard

InfraGuard includes a React admin dashboard for city traffic safety monitoring.

Current dashboard features:

- Supabase Auth admin login,
- city hotspot map,
- red incident dots for individual detected events,
- hotspot circles around incident clusters,
- daily report page,
- hotspot ranking table,
- fallback/LLM status warning,
- backend report loading through `/v1/reports/latest`.

The dashboard is designed for the final 24/7 CCTV workflow:

CCTV streams  
→ sampled detection  
→ event storage  
→ daily hotspot aggregation  
→ daily LLM/RAG report  
→ admin dashboard

The dashboard currently supports sample daily report data while the backend daily report generator is still being prepared.

## Authentication

The dashboard uses Supabase Auth for real admin login.

Backend report access can be protected with Supabase token verification by setting:

```env
REQUIRE_SUPABASE_AUTH=true