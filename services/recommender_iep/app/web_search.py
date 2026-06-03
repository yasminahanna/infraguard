import os

import httpx


def web_search_enabled() -> bool:
    return os.getenv("WEB_SEARCH_ENABLED", "false").lower() == "true"


def build_search_queries(
    event_types: list[str],
    risk_level: str,
    trend: str,
    metadata: dict,
) -> list[str]:
    location_text = str(metadata.get("location_name", "")).strip()
    country = str(metadata.get("country", "")).strip()
    city = str(metadata.get("city", "")).strip()

    event_text = " ".join(event_types).replace("_", " ")

    area = " ".join(part for part in [city, country, location_text] if part)

    queries = [
        f"road safety guidelines {event_text} {risk_level} risk traffic calming",
        f"traffic law road safety speed enforcement lane markings {area}",
        f"similar road safety hotspot case {event_text} {area}",
    ]

    return [query.strip() for query in queries if query.strip()]


def tavily_search(query: str, max_results: int) -> list[dict]:
    api_key = os.getenv("TAVILY_API_KEY")

    if not api_key:
        return []

    payload = {
        "api_key": api_key,
        "query": query,
        "search_depth": "basic",
        "max_results": max_results,
        "include_answer": False,
        "include_raw_content": False,
    }

    try:
        response = httpx.post(
            "https://api.tavily.com/search",
            json=payload,
            timeout=15,
        )
        response.raise_for_status()
    except Exception:
        return []

    data = response.json()
    results = data.get("results", [])

    cleaned_results = []

    for result in results:
        cleaned_results.append(
            {
                "source_type": "web",
                "query": query,
                "title": result.get("title", ""),
                "url": result.get("url", ""),
                "content": result.get("content", ""),
            }
        )

    return cleaned_results


def retrieve_web_context(
    event_types: list[str],
    risk_level: str,
    trend: str,
    metadata: dict,
) -> list[dict]:
    if not web_search_enabled():
        return []

    max_results = int(os.getenv("WEB_SEARCH_MAX_RESULTS", "3"))

    queries = build_search_queries(
        event_types=event_types,
        risk_level=risk_level,
        trend=trend,
        metadata=metadata,
    )

    context = []

    for query in queries:
        context.extend(tavily_search(query, max_results=max_results))

    return context[:max_results]