# Security and Robustness

## Public API Protection

The EEP Gateway requires an API key through the `X-API-Key` header.

Invalid or missing API keys return:

    {
      "detail": "Invalid or missing API key."
    }

## Input Validation

InfraGuard validates incoming requests using Pydantic schemas.

Validation includes:

- latitude range,
- longitude range,
- camera ID length,
- road segment ID length,
- maximum number of frames,
- confidence score range,
- allowed enum values.

## Payload Constraints

The EEP currently limits frame batches to a maximum of 8 frames.

This reduces:

- memory pressure,
- latency spikes,
- abuse risk,
- accidental oversized requests.

## Failure Modes

### Detection IEP Failure

Current behavior:

- The EEP treats Detection IEP failure as a hard failure because downstream services require detection events.

Planned behavior:

- Return a partial response if cached or previously computed detection evidence exists.

### Hotspot IEP Failure

Current behavior:

- The EEP treats Hotspot IEP failure as a hard failure because recommendations require hotspot evidence.

Planned behavior:

- Use current-sample-only risk scoring as a fallback.

### Recommender IEP Failure

Current behavior:

- The EEP returns an emergency conservative fallback response.
- The response explicitly records the fallback in `fallbacks_used`.

Planned behavior:

- Replace emergency static fallback with a classifier fallback trained on real public road safety data.

## Timeout Handling

The EEP uses HTTP client timeouts when calling internal services.

If an internal service times out, the EEP returns a controlled error or fallback response depending on the service.

## Secrets Management

Local development:

- Secrets are stored in `.env`.
- `.env` is excluded from Git using `.gitignore`.

Cloud deployment:

- API keys and OpenAI keys must be stored using the cloud provider's secret manager or protected environment variables.
- Secrets must not be committed to GitHub.

## Abuse Resistance

Implemented:

- API key authentication.
- Request validation.
- Frame count limit.

Planned:

- Rate limiting.
- Request body size limit at gateway or proxy level.
- IP-based throttling in deployment environment.

## Privacy Considerations

InfraGuard should avoid storing raw video unless required.

Preferred behavior:

- Process input frames.
- Store structured event metadata.
- Store confidence scores and risk results.
- Avoid storing faces, license plates, or personally identifying details.

Future privacy improvements:

- blur faces and license plates,
- delete raw frames after processing,
- document retention policy,
- store only aggregated hotspot evidence.