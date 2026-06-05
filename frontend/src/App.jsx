import { useMemo, useState } from "react";
import {
  Circle,
  CircleMarker,
  MapContainer,
  Marker,
  Popup,
  TileLayer,
} from "react-leaflet";
import dailyReport from "../../samples/daily_report_sample.json";

function riskClass(riskLevel) {
  if (riskLevel === "high") return "risk-high";
  if (riskLevel === "medium") return "risk-medium";
  return "risk-low";
}

function riskLabel(riskLevel) {
  if (riskLevel === "high") return "High Risk";
  if (riskLevel === "medium") return "Medium Risk";
  return "Low Risk";
}

function hotspotColor(riskLevel) {
  if (riskLevel === "high") return "#ef4444";
  if (riskLevel === "medium") return "#f59e0b";
  return "#22c55e";
}

function App() {
  const [activePage, setActivePage] = useState("overview");
  const [selectedSegmentId, setSelectedSegmentId] = useState(
    dailyReport.hotspots[0].road_segment_id
  );
  const [riskFilter, setRiskFilter] = useState("all");

  const filteredHotspots = useMemo(() => {
    if (riskFilter === "all") return dailyReport.hotspots;

    return dailyReport.hotspots.filter(
      (hotspot) => hotspot.risk_level === riskFilter
    );
  }, [riskFilter]);

  const selectedHotspot =
    dailyReport.hotspots.find(
      (hotspot) => hotspot.road_segment_id === selectedSegmentId
    ) || dailyReport.hotspots[0];

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-icon">IG</div>
          <div>
            <h1>InfraGuard</h1>
            <p>Admin Control Center</p>
          </div>
        </div>

        <nav className="nav">
          <button
            className={`nav-item ${activePage === "overview" ? "active" : ""}`}
            onClick={() => setActivePage("overview")}
          >
            City Overview
          </button>

          <button
            className={`nav-item ${activePage === "hotspots" ? "active" : ""}`}
            onClick={() => setActivePage("hotspots")}
          >
            Hotspots
          </button>

          <button
            className={`nav-item ${activePage === "reports" ? "active" : ""}`}
            onClick={() => setActivePage("reports")}
          >
            Daily Report
          </button>

          <button
            className={`nav-item ${activePage === "health" ? "active" : ""}`}
            onClick={() => setActivePage("health")}
          >
            System Health
          </button>
        </nav>

        <div className="sidebar-footer">
          <span>Report ID</span>
          <strong>{dailyReport.report_id}</strong>
        </div>
      </aside>

      <main className="dashboard">
        <header className="topbar">
          <div>
            <p className="eyebrow">Daily CCTV Safety Report</p>
            <h2>
              {dailyReport.city}, {dailyReport.country}
            </h2>
            <p className="muted">Generated at {dailyReport.generated_at}</p>
          </div>

          <div className="topbar-actions">
            <span className="live-dot"></span>
            <span>Monitoring active</span>
          </div>
        </header>

        {!dailyReport.recommender_status.using_llm_api && (
          <div className="warning-box top-warning">
            <strong>LLM API not connected</strong>
            <p>{dailyReport.recommender_status.warning}</p>
          </div>
        )}

        {activePage === "overview" && (
          <>
            <section className="summary-grid">
              <div className="metric-card">
                <span>Total Cameras</span>
                <strong>{dailyReport.summary.total_cameras}</strong>
              </div>

              <div className="metric-card">
                <span>Road Segments</span>
                <strong>{dailyReport.summary.total_road_segments}</strong>
              </div>

              <div className="metric-card">
                <span>Events Detected</span>
                <strong>{dailyReport.summary.total_events_detected}</strong>
              </div>

              <div className="metric-card danger">
                <span>High Risk Segments</span>
                <strong>{dailyReport.summary.high_risk_segments}</strong>
              </div>
            </section>

            <section className="content-grid">
              <MapPanel
                hotspots={filteredHotspots}
                riskFilter={riskFilter}
                setRiskFilter={setRiskFilter}
                setSelectedSegmentId={setSelectedSegmentId}
              />

              <HotspotDetails hotspot={selectedHotspot} />
            </section>

            <section className="panel table-panel">
              <div className="panel-header">
                <div>
                  <h3>Daily Hotspot Ranking</h3>
                  <p>Click a row to inspect a hotspot on the map.</p>
                </div>
              </div>

              <HotspotTable
                hotspots={dailyReport.hotspots}
                setSelectedSegmentId={setSelectedSegmentId}
                setActivePage={setActivePage}
              />
            </section>
          </>
        )}

        {activePage === "hotspots" && (
          <section className="panel table-panel">
            <div className="panel-header">
              <div>
                <h3>Daily Hotspot Ranking</h3>
                <p>Road segments ranked by risk score.</p>
              </div>

              <select
                value={riskFilter}
                onChange={(event) => setRiskFilter(event.target.value)}
              >
                <option value="all">All risks</option>
                <option value="high">High only</option>
                <option value="medium">Medium only</option>
                <option value="low">Low only</option>
              </select>
            </div>

            <HotspotTable
              hotspots={filteredHotspots}
              setSelectedSegmentId={setSelectedSegmentId}
              setActivePage={setActivePage}
            />
          </section>
        )}

        {activePage === "reports" && (
          <section className="panel">
            <div className="panel-header">
              <div>
                <h3>{dailyReport.daily_report.title}</h3>
                <p>Generated from the latest 24-hour CCTV monitoring window.</p>
              </div>
            </div>

            {!dailyReport.recommender_status.using_llm_api && (
              <div className="warning-box">
                <strong>Fallback report mode</strong>
                <p>{dailyReport.recommender_status.warning}</p>
              </div>
            )}

            <div className="report-grid">
              <div className="mini-card">
                <h4>Report Window</h4>
                <p>
                  <strong>Start:</strong> {dailyReport.report_window.start}
                </p>
                <p>
                  <strong>End:</strong> {dailyReport.report_window.end}
                </p>
              </div>

              <div className="mini-card">
                <h4>City Summary</h4>
                <p>Total events: {dailyReport.summary.total_events_detected}</p>
                <p>High risk: {dailyReport.summary.high_risk_segments}</p>
                <p>Medium risk: {dailyReport.summary.medium_risk_segments}</p>
                <p>Low risk: {dailyReport.summary.low_risk_segments}</p>
              </div>
            </div>

            <div className="section">
              <h4>Executive Summary</h4>
              <p className="long-report-text">
                {dailyReport.daily_report.executive_summary}
              </p>
            </div>

            <div className="section">
              <h4>Key Findings</h4>
              <ul className="report-list">
                {dailyReport.daily_report.key_findings.map((finding) => (
                  <li key={finding}>{finding}</li>
                ))}
              </ul>
            </div>

            <div className="section">
              <h4>Recommended Admin Actions</h4>
              <ul className="report-list">
                {dailyReport.daily_report.recommended_admin_actions.map(
                  (action) => (
                    <li key={action}>{action}</li>
                  )
                )}
              </ul>
            </div>

            <div className="section">
              <h4>Model Limitation Note</h4>
              <p className="long-report-text">
                {dailyReport.daily_report.model_limitation_note}
              </p>
            </div>

            <div className="section">
              <h4>Segment Recommendations</h4>
              <div className="recommendation-list">
                {dailyReport.hotspots.map((hotspot) => (
                  <div className="mini-card" key={hotspot.road_segment_id}>
                    <strong>{hotspot.location_name}</strong>
                    <span>{hotspot.recommendation.primary_intervention}</span>
                    <p>{hotspot.recommendation.explanation}</p>
                  </div>
                ))}
              </div>
            </div>
          </section>
        )}

        {activePage === "health" && (
          <section className="panel">
            <div className="panel-header">
              <div>
                <h3>System Health</h3>
                <p>Demo status of backend services.</p>
              </div>
            </div>

            <div className="health-grid">
              <HealthCard service="EEP Gateway" status="Online" />
              <HealthCard service="Detection IEP" status="Online" />
              <HealthCard service="Hotspot IEP" status="Online" />
              <HealthCard service="Recommender IEP" status="Fallback Ready" />
            </div>

            <div className="section">
              <h4>Production Readiness</h4>
              <p className="long-report-text">
                In production, this dashboard will read the latest generated
                daily report from the backend endpoint instead of static sample
                data. The intended flow is 24/7 CCTV sampling, detection, event
                storage, daily hotspot aggregation, LLM/RAG reporting, and
                dashboard display.
              </p>
            </div>
          </section>
        )}
      </main>
    </div>
  );
}

function MapPanel({ hotspots, riskFilter, setRiskFilter, setSelectedSegmentId }) {
  return (
    <div className="map-panel panel">
      <div className="panel-header">
        <div>
          <h3>City Hotspot Map</h3>
          <p>Red dots are incidents. Circles show hotspot areas.</p>
        </div>

        <select
          value={riskFilter}
          onChange={(event) => setRiskFilter(event.target.value)}
        >
          <option value="all">All risks</option>
          <option value="high">High only</option>
          <option value="medium">Medium only</option>
          <option value="low">Low only</option>
        </select>
      </div>

      <MapContainer center={[33.8955, 35.486]} zoom={14} className="map">
        <TileLayer
          attribution="&copy; OpenStreetMap contributors"
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        {hotspots.map((hotspot) => {
          const color = hotspotColor(hotspot.risk_level);

          return (
            <div key={hotspot.road_segment_id}>
              <Circle
                center={[hotspot.location.lat, hotspot.location.lon]}
                radius={hotspot.radius_meters || 120}
                pathOptions={{
                  color,
                  fillColor: color,
                  fillOpacity: 0.12,
                  weight: 2,
                }}
                eventHandlers={{
                  click: () => setSelectedSegmentId(hotspot.road_segment_id),
                }}
              />

              <Marker
                position={[hotspot.location.lat, hotspot.location.lon]}
                eventHandlers={{
                  click: () => setSelectedSegmentId(hotspot.road_segment_id),
                }}
              >
                <Popup>
                  <strong>{hotspot.location_name}</strong>
                  <br />
                  Hotspot area
                  <br />
                  Risk: {hotspot.risk_level}
                  <br />
                  Score: {hotspot.hotspot_score}
                </Popup>
              </Marker>

              {(hotspot.incidents || []).map((incident) => (
                <CircleMarker
                  key={incident.incident_id}
                  center={[incident.lat, incident.lon]}
                  radius={7}
                  pathOptions={{
                    color: "#991b1b",
                    fillColor: "#ef4444",
                    fillOpacity: 0.9,
                    weight: 2,
                  }}
                  eventHandlers={{
                    click: () => setSelectedSegmentId(hotspot.road_segment_id),
                  }}
                >
                  <Popup>
                    <strong>{incident.event_type}</strong>
                    <br />
                    Severity: {incident.severity}
                    <br />
                    Confidence: {incident.confidence}
                    <br />
                    Time: {incident.timestamp}
                  </Popup>
                </CircleMarker>
              ))}
            </div>
          );
        })}
      </MapContainer>
    </div>
  );
}

function HotspotDetails({ hotspot }) {
  return (
    <div className="panel details-panel">
      <div className="panel-header">
        <div>
          <h3>Selected Hotspot</h3>
          <p>{hotspot.location_name}</p>
        </div>
        <span className={`risk-pill ${riskClass(hotspot.risk_level)}`}>
          {riskLabel(hotspot.risk_level)}
        </span>
      </div>

      <div className="score-row">
        <div>
          <span>Hotspot Score</span>
          <strong>{hotspot.hotspot_score}</strong>
        </div>
        <div>
          <span>Trend</span>
          <strong>{hotspot.trend}</strong>
        </div>
        <div>
          <span>Events</span>
          <strong>{hotspot.event_count}</strong>
        </div>
      </div>

      <div className="section">
        <h4>Incident Points</h4>
        <p className="long-report-text">
          This hotspot contains {(hotspot.incidents || []).length} mapped
          incident points. Red dots on the map represent individual detected
          events, while the circle represents the hotspot area.
        </p>
      </div>

      <div className="section">
        <h4>Detected Event Types</h4>
        <div className="tag-list">
          {hotspot.top_event_types.map((eventType) => (
            <span className="tag" key={eventType}>
              {eventType}
            </span>
          ))}
        </div>
      </div>

      <div className="section recommendation-box">
        <div className="recommendation-header">
          <h4>Recommended Action</h4>
          <span className="provider-pill">{hotspot.recommendation.provider}</span>
        </div>

        <p className="intervention">
          {hotspot.recommendation.primary_intervention}
        </p>
        <p>{hotspot.recommendation.explanation}</p>

        <div className="action-list">
          {hotspot.recommendation.supporting_actions.map((action) => (
            <span key={action}>{action}</span>
          ))}
        </div>
      </div>
    </div>
  );
}

function HotspotTable({ hotspots, setSelectedSegmentId, setActivePage }) {
  return (
    <div className="hotspot-table">
      <div className="table-row table-head">
        <span>Segment</span>
        <span>Location</span>
        <span>Risk</span>
        <span>Score</span>
        <span>Recommendation</span>
      </div>

      {hotspots.map((hotspot) => (
        <button
          className="table-row table-button"
          key={hotspot.road_segment_id}
          onClick={() => {
            setSelectedSegmentId(hotspot.road_segment_id);
            setActivePage("overview");
          }}
        >
          <span>{hotspot.road_segment_id}</span>
          <span>{hotspot.location_name}</span>
          <span>
            <span className={`risk-pill small ${riskClass(hotspot.risk_level)}`}>
              {hotspot.risk_level}
            </span>
          </span>
          <span>{hotspot.hotspot_score}</span>
          <span>{hotspot.recommendation.primary_intervention}</span>
        </button>
      ))}
    </div>
  );
}

function HealthCard({ service, status }) {
  return (
    <div className="mini-card">
      <strong>{service}</strong>
      <span className="health-status">{status}</span>
    </div>
  );
}

export default App;