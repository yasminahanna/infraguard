# Observability

## Overview

InfraGuard exposes Prometheus-compatible metrics from every service through `/metrics`.

Services:

- EEP Gateway
- Detection IEP
- Hotspot IEP
- Recommender IEP

## Required Metrics

The final project requires meaningful per-service metrics, including latency, error rate, and throughput.

## EEP Gateway Metrics

Implemented or planned:

- total request count,
- end-to-end latency,
- downstream IEP failure count,
- fallback count,
- invalid API key count.

Current metrics:

- `eep_requests_total`
- `eep_latency_seconds`
- `eep_iep_failures_total`

## Detection IEP Metrics

Current metrics:

- `detection_requests_total`
- `detection_latency_seconds`
- `detection_events_total`

Planned ML-specific metrics:

- vehicle count distribution,
- mean confidence distribution,
- low-confidence rate,
- event type distribution.

## Hotspot IEP Metrics

Current metrics:

- `hotspot_requests_total`
- `hotspot_latency_seconds`
- `hotspot_score`
- `hotspot_level_total`

Planned metrics:

- trend distribution,
- high-risk segment count,
- baseline deviation.

## Recommender IEP Metrics

Current metrics:

- `recommender_requests_total`
- `recommender_latency_seconds`
- `recommender_llm_failures_total`
- `recommendation_type_total`

Planned metrics:

- LLM JSON validation failure rate,
- average LLM latency,
- fallback classifier usage,
- recommendation confidence distribution.

## Grafana Dashboard Plan

The dashboard will include:

- EEP request throughput,
- EEP latency p50 and p95,
- Detection latency,
- Detection event counts by type,
- Hotspot score distribution,
- Hotspot risk level counts,
- Recommender latency,
- LLM failure count,
- Recommendation type counts.

## Alerting-Ready Signals

Potential alert conditions:

- EEP p95 latency above threshold.
- Recommender LLM failure rate above threshold.
- Detection low-confidence rate above threshold.
- Internal endpoint unavailable.
- High-risk hotspot count spikes.

## Current Manual Metrics Checks

Commands:

    curl.exe http://localhost:8000/metrics
    curl.exe http://localhost:8001/metrics
    curl.exe http://localhost:8002/metrics
    curl.exe http://localhost:8003/metrics

## Next Observability Tasks

Next steps:

- Add Prometheus to Docker Compose.
- Add Grafana to Docker Compose.
- Create a dashboard JSON file.
- Add p50 and p95 panels.
- Add service-specific counters.
- Add fallback and failure panels.