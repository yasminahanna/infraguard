# Quality Assurance Strategy

## Test Levels

InfraGuard uses multiple test levels.

## Unit / API Tests

Implemented:

- Detection IEP API tests.
- Hotspot IEP API tests.
- Recommender IEP API tests.

These test:

- Health endpoints.
- Valid request behavior.
- Invalid request validation.
- Schema constraints.

## Integration Tests

Implemented:

- EEP integration test that calls the public gateway and verifies orchestration across Detection, Hotspot, and Recommender services.
- API key rejection test.
- Invalid payload rejection test.

## End-to-End Deployment Test

Planned:

- A test that calls the deployed public cloud endpoint.
- It will verify that the deployed system works outside local Docker.

## Golden Dataset Regression Tests

Planned:

A fixed set of representative road scenarios will be stored and tested on every change.

Each scenario will include:

- input metadata,
- expected event category range,
- expected hotspot risk range,
- expected recommendation category or acceptable alternatives.

## LLM Testing Strategy

LLM outputs are non-deterministic, so InfraGuard does not test exact text.

Instead, it tests:

- valid JSON response,
- schema compliance,
- allowed intervention values,
- evidence fields present,
- confidence within valid range,
- no invented fields beyond provided evidence.

## Failure Mode Tests

Implemented or planned:

- Missing OpenAI key.
- Recommender unavailable.
- Invalid API key.
- Invalid location.
- Too many frames.
- Invalid confidence score.