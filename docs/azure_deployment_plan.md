# Azure Deployment Plan

## Goal

Deploy InfraGuard for short-term grading and demonstration.

The hosted system should include:

- EEP Gateway
- Detection IEP
- Hotspot IEP
- Recommender IEP
- Admin dashboard later

## Preferred Azure Setup

Recommended backend option:

- Azure Container Apps

Recommended frontend option:

- Azure Static Web Apps

## Why Azure Container Apps

Azure Container Apps supports containerized services and environment variables. It is simpler than managing Kubernetes directly for a short-term project demo.

## Public and Internal Services

Public:

- EEP Gateway

Internal:

- Detection IEP
- Hotspot IEP
- Recommender IEP

If private networking is too complicated for the demo, internal services may be temporarily exposed with hard-to-guess URLs and protected configuration, but the preferred design is private internal communication.

## Required Container Images

Images needed:

- eep-gateway
- detection-iep
- hotspot-iep
- recommender-iep

## Required Secrets

Do not commit these values.

Required secrets:

- API_KEY
- OPENAI_API_KEY
- TAVILY_API_KEY if web RAG is enabled

## Required Config

Required non-secret environment variables:

- DETECTION_IEP_URL
- HOTSPOT_IEP_URL
- RECOMMENDER_IEP_URL
- LLM_PROVIDER
- LLM_MODEL
- LLM_TIMEOUT_SECONDS
- WEB_SEARCH_ENABLED
- WEB_SEARCH_MAX_RESULTS
- REQUEST_TIMEOUT_SECONDS
- MAX_FRAMES_PER_REQUEST

## Deployment Steps

1. Create Azure resource group.
2. Create Azure Container Registry or use GitHub Container Registry.
3. Build and push four Docker images.
4. Create Container App environment.
5. Deploy Detection IEP.
6. Deploy Hotspot IEP.
7. Deploy Recommender IEP.
8. Deploy EEP Gateway.
9. Set EEP public ingress.
10. Set environment variables and secrets.
11. Test EEP `/health`.
12. Test EEP `/v1/analyze`.
13. Run deployed E2E test.

## Resource Notes

Detection IEP is the heaviest service because it uses YOLO and CLIP.

Recommended starting resources for Detection IEP:

- at least 2 CPU
- at least 4 GiB memory

Other services can start smaller.

## Cost Controls

- Keep replicas at 1.
- Set billing alerts.
- Keep traffic low.
- Avoid repeated heavy image inference.
- Shut down services after grading.
- Do not store raw video.

## Verification

After deployment, run:

    pytest tests\e2e

With:

    DEPLOYED_EEP_URL
    DEPLOYED_API_KEY

The test should verify:

- public EEP responds,
- detection output exists,
- hotspot output exists,
- recommendation output exists.

## Rollback

Rollback plan:

- keep last stable image tag,
- redeploy previous image if health checks fail,
- document the rollback decision.