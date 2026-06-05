# Cloud Deployment Checklist

## Goal

Deploy InfraGuard so the EEP Gateway is publicly reachable and the full AI pipeline can be tested from outside the local machine.

## Required Public Endpoint

Only the EEP Gateway should be public.

Public endpoint:

    /v1/analyze

Internal services:

- Detection IEP
- Hotspot IEP
- Recommender IEP

These should not be publicly exposed unless the hosting platform requires it for the demo.

## Required Environment Variables

EEP Gateway:

    API_KEY
    DETECTION_IEP_URL
    HOTSPOT_IEP_URL
    RECOMMENDER_IEP_URL
    REQUEST_TIMEOUT_SECONDS
    MAX_FRAMES_PER_REQUEST

Recommender IEP:

    OPENAI_API_KEY
    LLM_PROVIDER
    LLM_MODEL
    LLM_TIMEOUT_SECONDS
    WEB_SEARCH_ENABLED
    TAVILY_API_KEY
    WEB_SEARCH_MAX_RESULTS

## Secrets

Do not commit real secrets.

Secrets include:

- API_KEY
- OPENAI_API_KEY
- TAVILY_API_KEY

Use the hosting provider secret manager or protected environment variables.

## Minimum Deployment Test

After deployment, run:

    pytest tests\e2e

With:

    DEPLOYED_EEP_URL
    DEPLOYED_API_KEY

Expected:

- EEP returns HTTP 200.
- Detection output exists.
- Hotspot output exists.
- Recommendation output exists.

## Health Checks

Verify:

    /health

For the EEP Gateway.

If internal service health endpoints are accessible privately, verify:

- Detection IEP health
- Hotspot IEP health
- Recommender IEP health

## Observability

Minimum deployment observability:

- service logs,
- request counts,
- latency,
- error count,
- fallback count.

Preferred:

- Prometheus and Grafana or cloud-managed equivalents.

## Rollback

Before deployment:

- tag the last stable commit,
- keep previous container image tag if using a registry.

Rollback if:

- EEP health fails,
- `/v1/analyze` fails,
- latency is too high,
- secrets are missing,
- recommender fails unexpectedly.

## Demo Evidence To Capture

Capture screenshots or logs of:

- deployed `/health`,
- deployed `/v1/analyze`,
- E2E test passing,
- dashboard or metrics view,
- cloud service configuration without secret values.