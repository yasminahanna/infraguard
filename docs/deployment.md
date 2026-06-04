# Deployment

## Local Development

InfraGuard runs locally using Docker Compose.

Command:

    docker compose up --build

Local service URLs:

- EEP Gateway: `http://localhost:8000`
- Detection IEP: `http://localhost:8001`
- Hotspot IEP: `http://localhost:8002`
- Recommender IEP: `http://localhost:8003`

## Docker Images

InfraGuard uses four service images:

- `infraguard-eep`
- `infraguard-detection-iep`
- `infraguard-hotspot-iep`
- `infraguard-recommender-iep`

This exceeds the minimum requirement of three Docker images.

## Cloud Deployment Target

Planned options:

- Azure Container Apps
- AWS ECS
- Google Cloud Run
- Render or Railway for fast deployment

Preferred initial target:

- Azure Container Apps or Google Cloud Run because they support containerized web services with environment variables and public URLs.

## Public API

The EEP Gateway must be publicly accessible.

The internal endpoints should either be:

- private services accessible only within the cloud network, or
- public services protected by internal tokens if private networking is not available.

## Environment Variables

Required:

    API_KEY=...
    DETECTION_IEP_URL=...
    HOTSPOT_IEP_URL=...
    RECOMMENDER_IEP_URL=...
    OPENAI_API_KEY=...
    LLM_MODEL=gpt-4o-mini
    LLM_TIMEOUT_SECONDS=12
    WEB_SEARCH_ENABLED=false
    TAVILY_API_KEY=
    WEB_SEARCH_MAX_RESULTS=3

## Secrets Management

Local:

- `.env`

Cloud:

- protected environment variables,
- cloud secret manager,
- no secrets committed to GitHub.

## Kubernetes

Kubernetes manifests are planned in the `k8s` folder.

Required resources:

- namespace,
- deployments,
- services,
- ingress,
- config map,
- secrets template.

## Rollback Plan

Initial rollback strategy:

- keep previous container image tag,
- redeploy previous image if health checks fail,
- use Git tag to identify last stable release.

Future rollback strategy:

- automated promotion or rollback decision from evaluation pipeline.

## Deployment Verification

After deployment, verify:

- public EEP `/health`,
- public EEP `/v1/analyze`,
- internal service health checks if accessible,
- API key rejection,
- invalid payload rejection,
- recommender fallback behavior,
- metrics endpoints.

## Cloud Deliverable Evidence

The final report should include:

- public API URL,
- deployment architecture diagram,
- environment variable list without secret values,
- screenshots or logs of successful deployed API calls,
- cloud cost estimate,
- rollback explanation.