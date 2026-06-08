import json
import os
from datetime import datetime, timezone
from pathlib import Path

import httpx
from openai import OpenAI

from app.reporter.aggregator import load_events, aggregate_segments
from app.reporter.feedback_store import load_recent_feedback, summarize_feedback_guidance
from app.web_search import retrieve_web_context

DEFAULT_LIMITATION_NOTE = (
    "This report was generated from stored traffic-event summaries. Detection uses YOLO + CLIP, "
    "segment risk is scored by the Hotspot IEP, and recommendations are produced by the Recommender "
    "IEP (OpenAI; optional Tavily web RAG). It does not store raw CCTV video."
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _score_segment(agg: dict, hotspot_url: str, window_end: str) -> dict:
    payload = {
        "camera_id": agg["camera_id"],
        "road_segment_id": agg["road_segment_id"],
        "timestamp": window_end,
        "location": agg["location"],
        "events": agg["reckless_events"],
        "metadata": agg["metadata"],
    }
    resp = httpx.post(f"{hotspot_url}/score", json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _recommend_segment(agg: dict, hotspot: dict, guidance: str = "") -> dict:
    # lazy import avoids a circular import with app.main
    from app.main import call_openai_recommender, RecommendationRequest

    # Feedback-conditioned generation: inject admin "lessons learned" via metadata,
    # which the existing recommender prompt already serializes (no existing fn changed).
    metadata = dict(agg["metadata"])
    if guidance:
        metadata["admin_feedback_guidance"] = guidance

    request = RecommendationRequest.model_validate(
        {
            "camera_id": agg["camera_id"],
            "road_segment_id": agg["road_segment_id"],
            "detection": {
                "vehicle_count": agg["vehicle_count"],
                "events_detected": agg["event_count"],
                "mean_confidence": agg["mean_confidence"],
                "event_types": agg["top_event_types"],
            },
            "hotspot": {
                "hotspot_score": hotspot["hotspot_score"],
                "risk_level": hotspot["risk_level"],
                "trend": hotspot["trend"],
                "cluster_id": hotspot["cluster_id"],
                "evidence": hotspot["evidence"],
            },
            "metadata": metadata,
        }
    )
    retrieved = retrieve_web_context(
        event_types=agg["top_event_types"],
        risk_level=hotspot["risk_level"],
        trend=hotspot["trend"],
        metadata=metadata,
    )
    rec = call_openai_recommender(request, retrieved).model_dump()
    rec["provider"] = "openai"
    return rec


def _fallback_recommendation(hotspot: dict) -> dict:
    return {
        "provider": "emergency_static_fallback",
        "primary_intervention": "add_warning_signage",
        "priority": hotspot["risk_level"],
        "supporting_actions": ["continue_monitoring", "review_segment_manually"],
        "explanation": (
            "The LLM recommender was unavailable for this segment, so InfraGuard returned "
            "a conservative emergency recommendation based on the hotspot score."
        ),
        "evidence_used": [
            f"hotspot_score={hotspot['hotspot_score']}",
            f"risk_level={hotspot['risk_level']}",
            f"trend={hotspot['trend']}",
        ],
        "confidence": 0.25,
    }


def _build_summary(data: dict, hotspots: list[dict]) -> dict:
    levels = [h["risk_level"] for h in hotspots]
    return {
        "total_cameras": data.get("total_cameras", len({h["camera_id"] for h in hotspots})),
        "total_road_segments": len(hotspots),
        "total_events_detected": sum(h["event_count"] for h in hotspots),
        "high_risk_segments": levels.count("high"),
        "medium_risk_segments": levels.count("medium"),
        "low_risk_segments": levels.count("low"),
    }


def _template_narrative(hotspots: list[dict], summary: dict) -> dict:
    top = hotspots[0] if hotspots else None
    return {
        "title": "Daily Road Safety Report",
        "executive_summary": (
            f"InfraGuard aggregated {summary['total_events_detected']} traffic-risk events across "
            f"{summary['total_road_segments']} monitored segments: {summary['high_risk_segments']} high-risk, "
            f"{summary['medium_risk_segments']} medium-risk, {summary['low_risk_segments']} low-risk."
            + (
                f" The highest-priority hotspot was {top['location_name']} "
                f"(score {top['hotspot_score']}, {top['trend']} trend)."
                if top
                else ""
            )
        ),
        "model_limitation_note": DEFAULT_LIMITATION_NOTE,
        "key_findings": [
            f"{h['location_name']}: score {h['hotspot_score']} ({h['risk_level']} risk, {h['trend']} trend), "
            f"{h['event_count']} events."
            for h in hotspots
        ][:6],
        "recommended_admin_actions": (
            [
                f"Review {h['location_name']} - {h['recommendation']['primary_intervention']}."
                for h in hotspots
                if h["risk_level"] in ("high", "medium")
            ][:6]
            or ["Continue monitoring all segments; no immediate intervention required."]
        ),
    }


def _llm_narrative(hotspots: list[dict], summary: dict, guidance: str = "") -> dict | None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    client = OpenAI(api_key=api_key, timeout=float(os.getenv("LLM_TIMEOUT_SECONDS", "60")))
    compact = [
        {
            "location_name": h["location_name"],
            "risk_level": h["risk_level"],
            "hotspot_score": h["hotspot_score"],
            "trend": h["trend"],
            "event_count": h["event_count"],
            "top_event_types": h["top_event_types"],
            "primary_intervention": h["recommendation"]["primary_intervention"],
        }
        for h in hotspots
    ]
    prompt = (
        "You are a city road-safety analyst. Using ONLY this aggregated 24h data, write a daily report. "
        "Return STRICT JSON with keys: title, executive_summary, model_limitation_note, "
        "key_findings (3-6 strings), recommended_admin_actions (3-6 strings). Do not invent facts.\n\n"
        f"summary: {json.dumps(summary)}\nsegments: {json.dumps(compact)}"
        + (f"\n\n{guidance}" if guidance else "")
    )
    try:
        resp = client.chat.completions.create(
            model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
            temperature=0.3,
            messages=[
                {"role": "system", "content": "Return strict JSON only."},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
        )
        p = json.loads(resp.choices[0].message.content)
        return {
            "title": p.get("title", "Daily Road Safety Report"),
            "executive_summary": p["executive_summary"],
            "model_limitation_note": p.get("model_limitation_note", DEFAULT_LIMITATION_NOTE),
            "key_findings": p.get("key_findings", [])[:6],
            "recommended_admin_actions": p.get("recommended_admin_actions", [])[:6],
        }
    except Exception:
        return None  # deterministic template fallback used by caller


def generate_daily_report() -> dict:
    events_path = os.getenv("EVENTS_PATH", "/app/samples/events_sample.json")
    hotspot_url = os.getenv("HOTSPOT_IEP_URL", "http://hotspot-iep:8002")
    store_path = os.getenv("REPORT_STORE_PATH", "/app/sample_data/daily_report_sample.json")

    data = load_events(events_path)

    # Merge admin-added camera events (uploaded + analyzed via the dashboard) so newly
    # onboarded cameras join the report alongside the seeded segments.
    added_path = os.getenv("ADDED_EVENTS_PATH", "/app/sample_data/added_events.json")
    if Path(added_path).exists():
        try:
            added = json.loads(Path(added_path).read_text(encoding="utf-8"))
            data.setdefault("segments", {}).update(added.get("segments", {}))
            data.setdefault("events", []).extend(added.get("events", []))
        except (json.JSONDecodeError, OSError):
            pass

    window = data.get("report_window", {"start": _now_iso(), "end": _now_iso()})
    aggregates = aggregate_segments(data)

    # Feedback flywheel: condition this batch on recent admin feedback.
    feedback_limit = int(os.getenv("FEEDBACK_CONTEXT_LIMIT", "50"))
    guidance = summarize_feedback_guidance(load_recent_feedback(feedback_limit))

    hotspots: list[dict] = []
    using_llm_api = True
    for agg in aggregates:
        hotspot = _score_segment(agg, hotspot_url, window["end"])
        try:
            rec = _recommend_segment(agg, hotspot, guidance)
        except Exception:
            rec = _fallback_recommendation(hotspot)
            using_llm_api = False
        hotspots.append(
            {
                "road_segment_id": agg["road_segment_id"],
                "camera_id": agg["camera_id"],
                "location_name": agg["location_name"],
                "location": agg["location"],
                "radius_meters": agg["radius_meters"],
                "incidents": agg["incidents"],
                "hotspot_score": hotspot["hotspot_score"],
                "risk_level": hotspot["risk_level"],
                "trend": hotspot["trend"],
                "event_count": agg["event_count"],
                "top_event_types": agg["top_event_types"],
                "recommendation": rec,
            }
        )

    summary = _build_summary(data, hotspots)
    narrative = (
        _llm_narrative(hotspots, summary, guidance) if using_llm_api else None
    ) or _template_narrative(hotspots, summary)

    city = data.get("city", "Unknown")
    report = {
        "report_id": f"daily_{datetime.now(timezone.utc).strftime('%Y_%m_%d')}_{city.lower()}",
        "city": city,
        "country": data.get("country", ""),
        "generated_at": _now_iso(),
        "report_window": window,
        "recommender_status": {
            "provider": "openai" if using_llm_api else "emergency_static_fallback",
            "using_llm_api": using_llm_api,
            "warning": ""
            if using_llm_api
            else "Some segments used fallback recommendations because the LLM recommender was unavailable.",
        },
        "summary": summary,
        "daily_report": narrative,
        "hotspots": hotspots,
    }
    Path(store_path).parent.mkdir(parents=True, exist_ok=True)
    with Path(store_path).open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    # Persist to report history as ONE entry per report_id (one per day): regenerating
    # the same day's report REPLACES the previous entry instead of stacking duplicates.
    history_path = os.getenv("REPORT_HISTORY_PATH", "/app/sample_data/reports_history.jsonl")
    Path(history_path).parent.mkdir(parents=True, exist_ok=True)

    kept: list[dict] = []
    if Path(history_path).exists():
        with Path(history_path).open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if entry.get("report_id") != report["report_id"]:
                    kept.append(entry)
    kept.append(report)

    with Path(history_path).open("w", encoding="utf-8") as f:
        for entry in kept:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    return report
