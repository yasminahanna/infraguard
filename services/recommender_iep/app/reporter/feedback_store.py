import json
import os
from datetime import datetime, timezone
from pathlib import Path


def _feedback_path() -> str:
    return os.getenv("FEEDBACK_PATH", "/app/sample_data/feedback.jsonl")


def append_feedback(record: dict) -> dict:
    """Append one admin feedback record (as a JSON line) to the feedback store."""
    record = {
        **record,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    path = Path(_feedback_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def load_recent_feedback(limit: int = 50) -> list[dict]:
    """Return the most recent feedback records (up to `limit`)."""
    path = Path(_feedback_path())
    if not path.exists():
        return []
    records: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines()[-limit:]:
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def summarize_feedback_guidance(records: list[dict], max_items: int = 8) -> str:
    """Turn recent feedback into a short 'lessons learned' block for LLM prompts."""
    lines: list[str] = []
    for r in records[-max_items:]:
        parts: list[str] = []
        if r.get("verdict"):
            parts.append(f"verdict={r['verdict']}")
        if r.get("corrected_intervention"):
            parts.append(f"admin_preferred={r['corrected_intervention']}")
        note = (r.get("note") or "").strip()
        if note:
            parts.append(f"note={note}")
        if parts:
            lines.append(f"- segment {r.get('road_segment_id', '')}: " + ", ".join(parts))
    if not lines:
        return ""
    return (
        "Admin feedback from previous reports (use as guidance; prefer admin-corrected "
        "interventions in similar situations, and avoid rejected ones):\n" + "\n".join(lines)
    )
