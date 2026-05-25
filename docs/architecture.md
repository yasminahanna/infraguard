# InfraGuard Architecture

## Purpose

InfraGuard is a production-oriented AI engineering system for road safety risk analysis. It detects risky driving behavior from camera inputs, identifies emerging hotspot segments, and generates infrastructure recommendations using an LLM-based recommender.

## High-Level Flow

Client / Demo User
→ EEP Gateway
→ Detection IEP
→ Hotspot IEP
→ Recommender IEP
→ Final response

## Services

### EEP Gateway

The External Endpoint is the public system boundary.

Responsibilities:

- Validate requests.
- Enforce API key authentication.
- Enforce payload constraints.
- Orchestrate internal endpoints.
- Handle timeouts and downstream failures.
- Return a unified response.

### Detection IEP

Internal Endpoint 1.

Responsibilities:

- Accept camera frame batches.
- Detect or estimate reckless-driving events.
- Return structured events, confidence scores, and severity labels.

Current implementation:

- Placeholder event detection for service integration.
- Future implementation will use computer vision models and OpenCV-based behavior analysis.

### Hotspot IEP

Internal Endpoint 2.

Responsibilities:

- Consume structured events from the Detection IEP.
- Compute hotspot risk score.
- Estimate trend relative to historical baseline.
- Return hotspot evidence.

### Recommender IEP

Internal Endpoint 3.

Responsibilities:

- Consume detection and hotspot evidence.
- Use an LLM to recommend infrastructure interventions.
- Validate strict JSON output.
- Return intervention, priority, supporting actions, explanation, and confidence.

Fallback plan:

- Current emergency fallback is handled by the EEP only if the recommender service is unavailable.
- Planned fallback is a classifier trained on real public road safety or traffic data.

## Why This Is Not a Monolith

InfraGuard intentionally separates concerns:

- Detection is computer vision oriented.
- Hotspot scoring is geospatial/temporal analytics oriented.
- Recommendation is LLM decision-support oriented.
- The EEP only orchestrates.

This improves testability, deployment flexibility, observability, and fault isolation.