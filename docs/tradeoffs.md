# Tradeoffs

## Tradeoff 1: LLM Quality vs Reliability

### Choice

InfraGuard uses an LLM recommender as the primary recommendation engine.

### Why

Infrastructure recommendations require explanation, contextual reasoning, and transparent evidence use. An LLM is suitable for converting structured detection and hotspot evidence into human-readable decision support.

### Rejected Option

A purely rule-based recommender.

### Why Rejected

A rule-based recommender is easier to test but weaker for nuanced infrastructure reasoning.

### Evidence To Collect

- LLM output validity rate.
- JSON schema validation failure rate.
- Latency p50 and p95.
- Recommendation consistency on golden inputs.

## Tradeoff 2: Cloud LLM API vs Local Ollama

### Choice

Start with OpenAI API for the primary LLM.

### Why

It is easier to deploy reliably in a cloud environment and avoids heavy GPU or CPU memory requirements.

### Rejected Option

Ollama-only deployment.

### Why Rejected

Ollama increases infrastructure burden and may complicate cloud deployment under a short deadline.

### Evidence To Collect

- Average LLM latency.
- Failure rate.
- Deployment cost.
- Memory and CPU requirements.

## Tradeoff 3: Micro-Batch Input vs Real-Time Streaming

### Choice

InfraGuard accepts batches of frames instead of full live streaming.

### Why

Micro-batch processing is easier to validate, test, deploy, and monitor within the project timeline.

### Rejected Option

Full real-time video streaming pipeline.

### Why Rejected

Streaming would require more complex buffering, state management, and failure handling.

### Evidence To Collect

- Latency as number of frames increases.
- Detection stability across sampled frame counts.
- Request failure rate.

## Tradeoff 4: Service Separation vs Simplicity

### Choice

InfraGuard uses separate services for EEP, Detection, Hotspot, and Recommender.

### Why

The project requires clear service boundaries and independent internal endpoints. Separation also improves fault isolation and observability.

### Rejected Option

Single FastAPI monolith.

### Why Rejected

A monolith would be faster to build but weaker architecturally and less aligned with the project requirements.

### Evidence To Collect

- Independent service health checks.
- Integration test results.
- Per-service latency metrics.

## Tradeoff 5: Emergency Static Fallback vs ML Classifier Fallback

### Current Choice

An emergency static fallback exists only at the EEP level if the Recommender IEP is unavailable.

### Final Intended Choice

Replace this with a classifier fallback trained on real public traffic or crash data.

### Why

A classifier fallback is more defensible and testable than static fallback logic.

### Evidence To Collect

- Classifier accuracy or validation score.
- Confidence calibration.
- Failure cases.
- Comparison with LLM recommendation outputs.

## Tradeoff 6: YOLO + CLIP vs Custom-Trained Event Model

### Choice

InfraGuard currently uses YOLOv8n for vehicle detection and CLIP zero-shot classification for event labels.

### Why

This gives real AI inference quickly without requiring a custom labeled dataset before the system architecture is complete.

### Rejected Option

Training a custom event classifier immediately.

### Why Rejected

A custom event classifier requires a reliable labeled dataset. Training without real labels would be misleading, and the project should not rely on synthetic labels for final claims.

### Evidence To Collect

- Vehicle count examples from real images.
- CLIP event classification outputs.
- Detection latency after model warm-up.
- Failure cases where CLIP misclassifies a scene.
- Comparison with a future dataset-trained classifier.
### Current Choice

The current Detection IEP uses placeholder event generation while the service architecture, tests, and orchestration are built first.

### Why

This allows the distributed system, contracts, validation, Dockerization, and integration tests to stabilize before adding heavier computer vision logic.

### Rejected Option

Start directly with a full YOLO or tracking pipeline before service orchestration.

### Why Rejected

Starting with computer vision first risks spending too much time on model setup before satisfying architecture, testing, deployment, and observability requirements.

### Evidence To Collect

- Detection model latency once implemented.
- Event confidence distribution.
- Behavior detection examples.
- Comparison against simpler baselines.