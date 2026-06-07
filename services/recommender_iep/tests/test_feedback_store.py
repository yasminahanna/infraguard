from app.reporter import feedback_store


def test_append_load_and_summarize(tmp_path, monkeypatch):
    fp = tmp_path / "feedback.jsonl"
    monkeypatch.setenv("FEEDBACK_PATH", str(fp))

    feedback_store.append_feedback({
        "report_id": "r1", "road_segment_id": "seg_a", "verdict": "reject",
        "corrected_intervention": "add_speed_bumps", "note": "residential area",
    })
    feedback_store.append_feedback({
        "report_id": "r1", "road_segment_id": "seg_b", "verdict": "accept",
    })

    records = feedback_store.load_recent_feedback(10)
    assert len(records) == 2
    assert records[0]["road_segment_id"] == "seg_a"
    assert "created_at" in records[0]

    guidance = feedback_store.summarize_feedback_guidance(records)
    assert "add_speed_bumps" in guidance
    assert "seg_a" in guidance


def test_summarize_empty_returns_blank():
    assert feedback_store.summarize_feedback_guidance([]) == ""
