# Quality Assurance Strategy

## Test Levels

InfraGuard uses multiple test levels.

## Unit and API Tests

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

Implemented placeholder:

- `tests/e2e/test_deployed_eep.py`

Current behavior:

- skipped unless `DEPLOYED_EEP_URL` and `DEPLOYED_API_KEY` are set.

Final behavior:

- after deployment, the test will call the hosted EEP `/v1/analyze` endpoint and verify that the deployed system returns detection, hotspot, and recommendation outputs.

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

## Current Test Commands

Detection IEP:

    cd services\detection_iep
    pytest

Hotspot IEP:

    cd services\hotspot_iep
    pytest

Recommender IEP:

    cd services\recommender_iep
    pytest

Integration tests:

    cd C:\Users\yasmi\infraguard
    pytest tests\integration

## Current Test Status

Current local test status:

- Detection IEP: 4 tests passing.
- Hotspot IEP: 5 tests passing.
- Recommender IEP: 5 tests passing.
- EEP integration: 3 tests passing.

## Regression Protection Plan

The regression suite will be expanded with golden examples.

Each golden example will check:

- whether the request is accepted,
- whether detection output remains within expected bounds,
- whether hotspot score remains within a tolerance band,
- whether recommendation category is acceptable,
- whether latency remains below a defined threshold.