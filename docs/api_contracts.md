# API Contracts

## Overview

InfraGuard uses one public External Endpoint and three Internal Endpoints.

The public endpoint is the EEP Gateway. The internal endpoints are:

- Detection IEP
- Hotspot IEP
- Recommender IEP

All services expose:

- `/health`
- `/metrics`

## EEP Gateway

### GET /health

Returns service health.

Example response:

    {
      "service": "eep_gateway",
      "status": "ok"
    }

### POST /v1/analyze

Public endpoint for full road-risk analysis.

Required header:

    X-API-Key: dev-secret-key

Example request:

    {
      "camera_id": "aub_gate_01",
      "road_segment_id": "segment_12",
      "timestamp": "2026-04-10T14:30:00Z",
      "location": {
        "lat": 33.9001,
        "lon": 35.4832
      },
      "frames_base64": [
        "fake_frame_1",
        "fake_frame_2",
        "fake_frame_3"
      ],
      "metadata": {
        "speed_limit_kmh": 50,
        "weather": "clear",
        "time_of_day": "evening",
        "historical_avg_events": 1.5
      }
    }

Example response:

    {
      "request_id": "req_abc123",
      "status": "completed",
      "detection": {},
      "hotspot": {},
      "recommendation": {},
      "fallbacks_used": [],
      "latency_ms": 200
    }

Validation constraints:

- `camera_id`: minimum 2 characters, maximum 100 characters.
- `road_segment_id`: minimum 2 characters, maximum 100 characters.
- `location.lat`: between -90 and 90.
- `location.lon`: between -180 and 180.
- `frames_base64`: minimum 1 frame, maximum 8 frames.

## Detection IEP

### GET /health

Returns service health.

Example response:

    {
      "service": "detection_iep",
      "status": "ok"
    }

### POST /detect

Input:

    {
      "camera_id": "aub_gate_01",
      "road_segment_id": "segment_12",
      "timestamp": "2026-04-10T14:30:00Z",
      "location": {
        "lat": 33.9001,
        "lon": 35.4832
      },
      "frames_base64": [
        "fake_frame_1"
      ],
      "metadata": {}
    }

Output:

    {
      "service": "detection_iep",
      "status": "completed",
      "vehicle_count": 2,
      "events": [
        {
          "event_type": "unsafe_proximity",
          "severity": "medium",
          "confidence": 0.74,
          "frame_index": 0,
          "bbox": {
            "x_min": 100,
            "y_min": 80,
            "x_max": 220,
            "y_max": 170
          },
          "explanation": "Vehicles appear close within the sampled region."
        }
      ],
      "mean_confidence": 0.74,
      "latency_ms": 1
    }

Allowed event types:

- `unsafe_proximity`
- `lane_region_violation`
- `possible_speeding`
- `wrong_direction_proxy`
- `high_density`

Allowed severity values:

- `low`
- `medium`
- `high`

Validation constraints:

- `location.lat`: between -90 and 90.
- `location.lon`: between -180 and 180.
- `frames_base64`: maximum 8 frames.
- `confidence`: between 0 and 1.

## Hotspot IEP

### GET /health

Returns service health.

Example response:

    {
      "service": "hotspot_iep",
      "status": "ok"
    }

### POST /score

Input:

    {
      "camera_id": "aub_gate_01",
      "road_segment_id": "segment_12",
      "timestamp": "2026-04-10T14:30:00Z",
      "location": {
        "lat": 33.9001,
        "lon": 35.4832
      },
      "events": [
        {
          "event_type": "unsafe_proximity",
          "severity": "medium",
          "confidence": 0.74,
          "frame_index": 0,
          "explanation": "Vehicles appear close."
        }
      ],
      "metadata": {
        "historical_avg_events": 1.5
      }
    }

Output:

    {
      "service": "hotspot_iep",
      "status": "completed",
      "road_segment_id": "segment_12",
      "hotspot_score": 0.45,
      "risk_level": "medium",
      "trend": "increasing",
      "cluster_id": "cluster_012",
      "evidence": [
        {
          "label": "event_count",
          "value": "1"
        }
      ],
      "latency_ms": 1
    }

Allowed risk levels:

- `low`
- `medium`
- `high`

Allowed trends:

- `stable`
- `increasing`
- `decreasing`

Validation constraints:

- `hotspot_score`: between 0 and 1.
- Event `confidence`: between 0 and 1.
- Event `severity`: must be `low`, `medium`, or `high`.

## Recommender IEP

### GET /health

Returns service health.

Example response:

    {
      "service": "recommender_iep",
      "status": "ok",
      "provider": "openai",
      "model": "gpt-4o-mini",
      "has_api_key": false
    }

### POST /recommend

Input:

    {
      "camera_id": "aub_gate_01",
      "road_segment_id": "segment_12",
      "detection": {
        "vehicle_count": 6,
        "events_detected": 3,
        "mean_confidence": 0.743,
        "event_types": [
          "unsafe_proximity",
          "high_density",
          "possible_speeding"
        ]
      },
      "hotspot": {
        "hotspot_score": 0.79,
        "risk_level": "high",
        "trend": "increasing",
        "cluster_id": "cluster_012",
        "evidence": [
          {
            "label": "event_count",
            "value": "3"
          }
        ]
      },
      "metadata": {
        "speed_limit_kmh": 50,
        "weather": "clear",
        "time_of_day": "evening"
      }
    }

Output:

    {
      "service": "recommender_iep",
      "status": "completed",
      "provider": "openai",
      "model": "gpt-4o-mini",
      "recommendation": {
        "primary_intervention": "install_speed_camera",
        "priority": "high",
        "supporting_actions": [
          "increase_enforcement",
          "add_warning_signage"
        ],
        "explanation": "Recommendation based on hotspot and detection evidence.",
        "evidence_used": [
          "hotspot_score=0.79",
          "risk_level=high"
        ],
        "confidence": 0.75
      },
      "latency_ms": 1000
    }

Allowed primary interventions:

- `install_speed_camera`
- `add_warning_signage`
- `repaint_lane_markings`
- `improve_lighting`
- `add_speed_bumps`
- `increase_enforcement`
- `review_signal_timing`
- `redesign_intersection`
- `no_action_monitor`

Allowed priority values:

- `low`
- `medium`
- `high`

Validation constraints:

- `vehicle_count`: must be greater than or equal to 0.
- `events_detected`: must be greater than or equal to 0.
- `mean_confidence`: between 0 and 1.
- `hotspot_score`: between 0 and 1.
- `risk_level`: must be `low`, `medium`, or `high`.
- `trend`: must be `stable`, `increasing`, or `decreasing`.

## Error Behavior

### Invalid API Key

Returned by the EEP Gateway:

    {
      "detail": "Invalid or missing API key."
    }

### Invalid Payload

FastAPI returns HTTP 422 with validation details.

### Recommender Unavailable

The EEP returns a completed response with:

    {
      "fallbacks_used": [
        "recommender_service_unavailable"
      ]
    }

The response includes an emergency conservative recommendation. This is not the final intended fallback model. The planned fallback is a classifier trained on real public traffic or crash data.