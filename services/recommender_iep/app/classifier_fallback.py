from pathlib import Path
from typing import Any

import joblib


MODEL_PATH = Path(__file__).resolve().parents[1] / "model" / "fallback_classifier.joblib"


INTERVENTION_SUPPORTING_ACTIONS = {
    "install_speed_camera": [
        "increase_enforcement",
        "add_warning_signage",
    ],
    "add_warning_signage": [
        "continue_monitoring",
        "review_segment_manually",
    ],
    "repaint_lane_markings": [
        "add_warning_signage",
        "review_signal_timing",
    ],
    "improve_lighting": [
        "repaint_lane_markings",
        "add_warning_signage",
    ],
    "add_speed_bumps": [
        "add_warning_signage",
        "increase_enforcement",
    ],
    "increase_enforcement": [
        "add_warning_signage",
        "continue_monitoring",
    ],
    "review_signal_timing": [
        "repaint_lane_markings",
        "add_warning_signage",
    ],
    "redesign_intersection": [
        "review_signal_timing",
        "increase_enforcement",
    ],
    "no_action_monitor": [
        "continue_monitoring",
    ],
}


def _risk_level_to_number(risk_level: str) -> int:
    if risk_level == "high":
        return 2
    if risk_level == "medium":
        return 1
    return 0


def _trend_to_number(trend: str) -> int:
    if trend == "increasing":
        return 1
    if trend == "decreasing":
        return -1
    return 0


def build_classifier_features(payload: Any) -> dict:
    event_types = set(payload.detection.event_types)
    metadata = payload.metadata

    return {
        "hotspot_score": float(payload.hotspot.hotspot_score),
        "risk_level_num": _risk_level_to_number(payload.hotspot.risk_level),
        "trend_num": _trend_to_number(payload.hotspot.trend),
        "vehicle_count": int(payload.detection.vehicle_count),
        "events_detected": int(payload.detection.events_detected),
        "mean_confidence": float(payload.detection.mean_confidence),
        "speed_limit_kmh": float(metadata.get("speed_limit_kmh", 50)),
        "weather": str(metadata.get("weather", "unknown")).lower(),
        "time_of_day": str(metadata.get("time_of_day", "unknown")).lower(),
        "has_unsafe_proximity": int("unsafe_proximity" in event_types),
        "has_lane_region_violation": int("lane_region_violation" in event_types),
        "has_possible_speeding": int("possible_speeding" in event_types),
        "has_wrong_direction_proxy": int("wrong_direction_proxy" in event_types),
        "has_high_density": int("high_density" in event_types),
    }


def priority_from_risk(hotspot_score: float, trend: str) -> str:
    if hotspot_score >= 0.70:
        return "high"
    if hotspot_score >= 0.45 and trend == "increasing":
        return "high"
    if hotspot_score >= 0.35:
        return "medium"
    return "low"


def classifier_recommendation(payload: Any) -> dict:
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Fallback classifier model not found at {MODEL_PATH}. "
            "Run train_fallback_classifier.py first."
        )

    model = joblib.load(MODEL_PATH)
    features = build_classifier_features(payload)

    predicted_intervention = model.predict([features])[0]

    probabilities = model.predict_proba([features])[0]
    confidence = float(max(probabilities))

    priority = priority_from_risk(
        hotspot_score=payload.hotspot.hotspot_score,
        trend=payload.hotspot.trend,
    )

    supporting_actions = INTERVENTION_SUPPORTING_ACTIONS.get(
        predicted_intervention,
        ["continue_monitoring"],
    )

    explanation = (
        "The OpenAI recommender was unavailable, so InfraGuard used a local "
        "RandomForest fallback classifier trained on policy-labeled road-risk scenarios. "
        f"The classifier selected '{predicted_intervention}' using hotspot score, trend, "
        "event types, confidence, vehicle count, weather, and time-of-day features."
    )

    evidence_used = [
        f"hotspot_score={payload.hotspot.hotspot_score}",
        f"risk_level={payload.hotspot.risk_level}",
        f"trend={payload.hotspot.trend}",
        f"events_detected={payload.detection.events_detected}",
        f"mean_confidence={payload.detection.mean_confidence}",
        f"event_types={payload.detection.event_types}",
    ]

    return {
        "primary_intervention": predicted_intervention,
        "priority": priority,
        "supporting_actions": supporting_actions,
        "explanation": explanation,
        "evidence_used": evidence_used,
        "confidence": round(confidence, 3),
    }