# MLOps and LLMOps Strategy

## Overview

InfraGuard requires lifecycle logic for AI components. The system includes computer vision detection, hotspot scoring, and LLM recommendation.

## Detection Lifecycle

Current state:

- placeholder detection logic for service integration.

Planned state:

- computer vision model or OpenCV pipeline,
- evaluation on selected traffic dataset,
- confidence and event quality tracking.

Metrics:

- mean confidence,
- low-confidence rate,
- event count stability,
- latency p50 and p95.

## Hotspot Lifecycle

The hotspot service uses structured detection events and metadata.

Evaluation metrics:

- hotspot score consistency,
- severity calibration,
- trend accuracy against historical baseline,
- sensitivity to event count changes.

## Recommender LLMOps

The LLM recommender must return strict JSON.

Validation:

- schema validation,
- allowed intervention values,
- evidence fields required,
- confidence range validation.

Prompt management:

- prompt versions will be tracked in Git,
- prompt changes must include evaluation notes,
- golden inputs will be used to compare outputs before promotion.

## RAG Strategy

The Recommender IEP supports optional web retrieval before calling the LLM.

RAG input signals:

- detected event types,
- hotspot risk level,
- hotspot trend,
- city,
- country,
- location name,
- road metadata.

Retrieved context may include:

- road safety guidance,
- traffic enforcement information,
- similar hotspot examples,
- location-specific public information.

The recommender must not claim that a law or regulation applies unless the retrieved source clearly supports it.

The retrieved context is returned in the API response for transparency.

## Fallback Classifier Plan

The final fallback should be a classifier trained on real public traffic or crash data.

The classifier will not be trained on synthetic labels.

Possible prediction targets:

- risk class,
- incident severity,
- violation type,
- hotspot severity.

The LLM can then use this structured fallback output to generate final recommendations when available.

## Experiment Tracking

Planned tool:

- MLflow or equivalent.

Tracked fields:

- dataset version,
- model version,
- prompt version,
- evaluation metrics,
- latency,
- failure rate,
- promotion decision.

## Promotion Thresholds

Example thresholds:

- LLM JSON validity rate greater than or equal to 95%.
- Recommender schema validation pass rate greater than or equal to 95%.
- Detection p95 latency below target.
- Hotspot golden regression pass rate greater than or equal to 90%.
- Fallback classifier validation score above selected threshold.

## Rollback Logic

A model or prompt version should not be promoted if:

- schema validation failures increase,
- golden regression tests fail,
- latency exceeds threshold,
- recommendation confidence drops significantly,
- outputs violate evidence-grounding rules.

## Planned Automated Pipeline

The planned lifecycle pipeline will:

1. Run tests.
2. Run golden regression scenarios.
3. Run LLM schema validation scenarios.
4. Log results to MLflow or equivalent.
5. Compare metrics to thresholds.
6. Produce a promotion or rejection decision.
7. Document the decision in the repository.