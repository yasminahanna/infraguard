from app.web_search import build_search_queries, retrieve_web_context


def test_build_search_queries_uses_events_and_location():
    queries = build_search_queries(
        event_types=["unsafe_proximity", "high_density"],
        risk_level="high",
        trend="increasing",
        metadata={
            "city": "Beirut",
            "country": "Lebanon",
            "location_name": "AUB Gate area",
        },
    )

    assert len(queries) == 3
    assert "unsafe proximity high density" in queries[0]
    assert "high risk" in queries[0]
    assert "Beirut Lebanon AUB Gate area" in queries[1]


def test_retrieve_web_context_returns_empty_when_disabled(monkeypatch):
    monkeypatch.setenv("WEB_SEARCH_ENABLED", "false")

    context = retrieve_web_context(
        event_types=["reckless_driving"],
        risk_level="medium",
        trend="stable",
        metadata={
            "city": "Beirut",
            "country": "Lebanon",
        },
    )

    assert context == []


def test_retrieve_web_context_returns_empty_without_api_key(monkeypatch):
    monkeypatch.setenv("WEB_SEARCH_ENABLED", "true")
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)

    context = retrieve_web_context(
        event_types=["reckless_driving"],
        risk_level="medium",
        trend="stable",
        metadata={
            "city": "Beirut",
            "country": "Lebanon",
        },
    )

    assert context == []