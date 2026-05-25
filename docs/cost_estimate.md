# Cost Estimate

## Cost Drivers

InfraGuard cost depends on:

- number of API requests,
- number of frames per request,
- computer vision inference cost,
- LLM recommendation calls,
- cloud container runtime,
- monitoring stack,
- storage for logs and metrics.

## Local Development Cost

Local Docker Compose development has no direct cloud cost.

## Cloud Runtime Cost

Expected services:

- EEP Gateway container,
- Detection IEP container,
- Hotspot IEP container,
- Recommender IEP container,
- Prometheus or managed metrics,
- Grafana or managed dashboard.

Small demo deployment estimate:

- low CPU containers,
- minimal memory,
- low traffic,
- expected cost depends on provider free tier and usage.

## LLM Cost

The LLM recommender is a variable cost.

Cost drivers:

- prompt length,
- response length,
- number of requests,
- model choice.

Cost reduction strategies:

- keep prompt compact,
- send structured summaries instead of raw frames,
- use caching for repeated scenarios,
- use classifier fallback for non-critical cases,
- use lower-cost model for demo.

## Computer Vision Cost

Current placeholder detection has minimal cost.

Future YOLO or OpenCV detection cost depends on:

- frame count,
- image resolution,
- CPU vs GPU inference,
- model size.

Cost reduction strategies:

- frame sampling,
- image resizing,
- lightweight detector,
- batch size limits.

## Monitoring Cost

Prometheus and Grafana can run locally or in containers.

Cloud cost depends on:

- retention period,
- scrape frequency,
- managed vs self-hosted monitoring.

## Estimated Demo Budget

For a short-lived demo deployment:

- expected low cloud cost if containers are small and traffic is limited,
- LLM cost should remain low because demo requests are few,
- monitoring can be local or low-retention.

Final exact numbers will be added after choosing the cloud provider.

## Cost Risks

Main cost risks:

- running large computer vision models continuously,
- using high-cost LLM models,
- storing raw video,
- high monitoring retention,
- leaving cloud services running after the demo.

## Cost Controls

Planned controls:

- frame limit per request,
- API key protection,
- low-cost model selection,
- no raw video retention by default,
- short monitoring retention for demo,
- shutdown script or manual shutdown checklist after presentation.