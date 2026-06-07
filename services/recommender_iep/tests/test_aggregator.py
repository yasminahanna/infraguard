from app.reporter.aggregator import aggregate_segments


def test_aggregate_groups_and_maps_shapes():
    data = {
        "segments": {
            "seg_a": {
                "camera_id": "cam_a",
                "location_name": "A",
                "location": {"lat": 1.0, "lon": 2.0},
                "radius_meters": 120,
                "metadata": {"historical_avg_events": 2},
            }
        },
        "events": [
            {
                "incident_id": "i1",
                "road_segment_id": "seg_a",
                "event_type": "high_density",
                "severity": "high",
                "confidence": 0.9,
                "timestamp": "t1",
                "lat": 1.0,
                "lon": 2.0,
                "vehicle_count": 5,
            },
            {
                "incident_id": "i2",
                "road_segment_id": "seg_a",
                "event_type": "high_density",
                "severity": "medium",
                "confidence": 0.6,
                "timestamp": "t2",
                "lat": 1.1,
                "lon": 2.1,
            },
        ],
    }
    [seg] = aggregate_segments(data)
    assert seg["road_segment_id"] == "seg_a"
    assert seg["event_count"] == 2
    assert seg["top_event_types"] == ["high_density"]
    assert seg["incidents"][0]["incident_id"] == "i1"  # dashboard shape
    assert seg["reckless_events"][0]["frame_index"] == 0  # hotspot shape (required)
    assert "lat" not in seg["reckless_events"][0]
    assert seg["vehicle_count"] == 5
