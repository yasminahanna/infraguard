from dataclasses import dataclass
from functools import lru_cache

import numpy as np
import torch
from PIL import Image
from transformers import CLIPModel, CLIPProcessor


EVENT_LABEL_PROMPTS = {
    "normal_traffic": "a normal traffic scene with ordinary driving",
    "high_density": "a dense traffic congestion scene with many vehicles",
    "reckless_driving": "a traffic scene showing reckless or aggressive driving",
    "lane_violation": "a vehicle violating lane markings or driving outside its lane",
    "wrong_direction_proxy": "a vehicle driving in the wrong direction",
    "phone_usage_possible": "a driver visibly using a mobile phone while driving",
    "unsafe_proximity": "vehicles driving dangerously close to each other",
}


@dataclass
class EventClassification:
    event_type: str
    confidence: float
    prompt: str


@lru_cache(maxsize=1)
def get_clip_components() -> tuple[CLIPModel, CLIPProcessor, torch.device]:
    model_name = "openai/clip-vit-base-patch32"

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    processor = CLIPProcessor.from_pretrained(model_name)
    model = CLIPModel.from_pretrained(model_name)
    model.to(device)
    model.eval()

    return model, processor, device


def classify_frame_events(
    image: Image.Image,
    confidence_threshold: float = 0.25,
) -> list[EventClassification]:
    model, processor, device = get_clip_components()

    labels = list(EVENT_LABEL_PROMPTS.keys())
    prompts = [EVENT_LABEL_PROMPTS[label] for label in labels]

    inputs = processor(
        text=prompts,
        images=image,
        return_tensors="pt",
        padding=True,
    )

    inputs = {
        key: value.to(device)
        for key, value in inputs.items()
    }

    with torch.no_grad():
        outputs = model(**inputs)
        logits_per_image = outputs.logits_per_image
        probabilities = logits_per_image.softmax(dim=1).cpu().numpy()[0]

    classifications: list[EventClassification] = []

    for label, prompt, probability in zip(labels, prompts, probabilities):
        confidence = float(probability)

        if confidence >= confidence_threshold:
            classifications.append(
                EventClassification(
                    event_type=label,
                    confidence=round(confidence, 3),
                    prompt=prompt,
                )
            )

    classifications.sort(key=lambda item: item.confidence, reverse=True)

    return classifications


def summarize_classifications(
    classifications_by_frame: list[list[EventClassification]],
) -> list[EventClassification]:
    best_by_event_type: dict[str, EventClassification] = {}

    for frame_classifications in classifications_by_frame:
        for classification in frame_classifications:
            current_best = best_by_event_type.get(classification.event_type)

            if current_best is None or classification.confidence > current_best.confidence:
                best_by_event_type[classification.event_type] = classification

    summarized = list(best_by_event_type.values())
    summarized.sort(key=lambda item: item.confidence, reverse=True)

    return summarized