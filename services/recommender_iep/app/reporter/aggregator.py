import json
from collections import Counter
from pathlib import Path


def load_events(events_path: str) -> dict:
    with Path(events_path).open("r", encoding="utf-8") as f:
        return json.load(f)


def _mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 3) if values else 0.0


def aggregate_segments(data: dict) -> list[dict]:
    """Group the stored event stream by road segment and shape it for both the
    dashboard (incidents) and the hotspot scorer (RecklessEvent)."""
    segments_meta = data.get("segments", {})
    grouped: dict[str, list[dict]] = {}
    for event in data.get("events", []):
        grouped.setdefault(event["road_segment_id"], []).append(event)

    aggregates: list[dict] = []
    for segment_id, seg_events in grouped.items():
        meta = segments_meta.get(segment_id, {})
        confidences = [float(e.get("confidence", 0.0)) for e in seg_events]
        top_event_types = [
            t
            for t, _ in Counter(
                e.get("event_type", "unknown") for e in seg_events
            ).most_common(3)
        ]

        incidents = [
            {
                k: e.get(k)
                for k in (
                    "incident_id",
                    "event_type",
                    "severity",
                    "confidence",
                    "timestamp",
                    "lat",
                    "lon",
                )
            }
            for e in seg_events
        ]
        # hotspot /score shape: frame_index REQUIRED, no lat/lon (verified contract)
        reckless_events = [
            {
                "event_type": e.get("event_type"),
                "severity": e.get("severity"),
                "confidence": float(e.get("confidence", 0.0)),
                "frame_index": idx,
            }
            for idx, e in enumerate(seg_events)
        ]
        vehicle_counts = [
            int(e["vehicle_count"]) for e in seg_events if "vehicle_count" in e
        ]

        aggregates.append(
            {
                "road_segment_id": segment_id,
                "camera_id": meta.get(
                    "camera_id", seg_events[0].get("camera_id", "unknown")
                ),
                "location_name": meta.get("location_name", segment_id),
                "location": meta.get(
                    "location",
                    {"lat": seg_events[0].get("lat"), "lon": seg_events[0].get("lon")},
                ),
                "radius_meters": meta.get("radius_meters", 150),
                "metadata": meta.get("metadata", {}),
                "incidents": incidents,
                "reckless_events": reckless_events,
                "event_count": len(seg_events),
                "top_event_types": top_event_types,
                "mean_confidence": _mean(confidences),
                "vehicle_count": max(vehicle_counts) if vehicle_counts else len(seg_events),
            }
        )

    aggregates.sort(key=lambda a: a["event_count"], reverse=True)
    return aggregates
