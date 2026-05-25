# Demo Script

## Goal

Show that InfraGuard is a deployed, production-oriented AI system with multiple services, validation, observability, and controlled failure behavior.

## Demo Scenario 1: Health Checks

Show all services are running.

Commands:

    curl.exe http://localhost:8000/health
    curl.exe http://localhost:8001/health
    curl.exe http://localhost:8002/health
    curl.exe http://localhost:8003/health

Expected:

- EEP Gateway healthy.
- Detection IEP healthy.
- Hotspot IEP healthy.
- Recommender IEP healthy.

## Demo Scenario 2: End-to-End Analysis

Call the public EEP endpoint.

Command:

    curl.exe -X POST http://localhost:8000/v1/analyze `
      -H "Content-Type: application/json" `
      -H "X-API-Key: dev-secret-key" `
      --data-binary "@samples/analyze_request.json"

Show:

- detection result,
- hotspot score,
- recommendation result,
- request ID,
- latency.

## Demo Scenario 3: Security Validation

Call with wrong API key.

Command:

    curl.exe -X POST http://localhost:8000/v1/analyze `
      -H "Content-Type: application/json" `
      -H "X-API-Key: wrong-key" `
      --data-binary "@samples/analyze_request.json"

Expected:

    {
      "detail": "Invalid or missing API key."
    }

## Demo Scenario 4: Payload Validation

Call with invalid payload.

Command:

    curl.exe -X POST http://localhost:8000/v1/analyze `
      -H "Content-Type: application/json" `
      -H "X-API-Key: dev-secret-key" `
      --data-binary "@samples/bad_analyze_request.json"

Expected:

- validation error,
- no internal processing.

## Demo Scenario 5: Recommender Failure Behavior

Run without OpenAI API key or temporarily disable the recommender service.

Expected:

- EEP still returns a completed response,
- `fallbacks_used` records recommender failure,
- recommendation clearly states emergency fallback.

## Demo Scenario 6: Tests

Run service tests.

Detection:

    cd services\detection_iep
    pytest

Hotspot:

    cd ..\hotspot_iep
    pytest

Recommender:

    cd ..\recommender_iep
    pytest

Run integration tests:

    cd C:\Users\yasmi\infraguard
    pytest tests\integration

## Demo Scenario 7: Observability

Open metrics endpoints.

Commands:

    curl.exe http://localhost:8000/metrics
    curl.exe http://localhost:8001/metrics
    curl.exe http://localhost:8002/metrics
    curl.exe http://localhost:8003/metrics

Show:

- request counters,
- latency histograms,
- event counters,
- hotspot score metrics,
- recommender failure metrics.

## Demo Scenario 8: Architecture Explanation

Explain:

- EEP is the public system boundary.
- Detection IEP handles risky behavior events.
- Hotspot IEP handles risk scoring and trend.
- Recommender IEP handles LLM-based infrastructure advice.
- The system is not a monolith.
- The services are independently testable and observable.

## Demo Scenario 9: Tradeoffs

Show the tradeoffs document and explain:

- LLM quality vs reliability.
- Cloud LLM vs Ollama.
- Micro-batch vs streaming.
- Service separation vs simplicity.
- Emergency fallback now vs real classifier fallback later.