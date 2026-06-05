import { useEffect, useMemo, useState } from "react";
import {
  Circle,
  CircleMarker,
  MapContainer,
  Marker,
  Popup,
  TileLayer,
} from "react-leaflet";
import { getLatestReport } from "./api";
import { supabase } from "./supabaseClient";

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
  const [session, setSession] = useState(null);
  const [authLoading, setAuthLoading] = useState(true);
  const [dailyReport, setDailyReport] = useState(null);
  const [reportSource, setReportSource] = useState("sample");
  const [activePage, setActivePage] = useState("overview");
  const [selectedSegmentId, setSelectedSegmentId] = useState(null);
  const [riskFilter, setRiskFilter] = useState("all");

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setAuthLoading(false);
    });

    const { data: listener } = supabase.auth.onAuthStateChange(
      (_event, newSession) => {
        setSession(newSession);
      }
    );

    return () => {
      listener.subscription.unsubscribe();
    };
  }, []);

  useEffect(() => {
    if (!session) return;

    getLatestReport().then(({ report, source }) => {
      setDailyReport(report);
      setReportSource(source);
      setSelectedSegmentId(report.hotspots[0].road_segment_id);
    });
  }, [session]);

  const filteredHotspots = useMemo(() => {
    if (!dailyReport) return [];
    if (riskFilter === "all") return dailyReport.hotspots;

    return dailyReport.hotspots.filter(
      (hotspot) => hotspot.risk_level === riskFilter
    );
  }, [dailyReport, riskFilter]);

  async function handleLogout() {
    await supabase.auth.signOut();
    setDailyReport(null);
    setSelectedSegmentId(null);
  }

  if (authLoading) {
    return <div className="loading-screen">Checking admin session...</div>;
  }

  if (!session) {
    return <LoginScreen />;
  }

  if (!dailyReport || !selectedSegmentId) {
    return <div className="loading-screen">Loading InfraGuard dashboard...</div>;
  }

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
          <span>Signed in as</span>
          <strong>{session.user.email}</strong>

          <span className="footer-label">Report ID</span>
          <strong>{dailyReport.report_id}</strong>

          <button className="logout-button" onClick={handleLogout}>
            Log out
          </button>
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
            <span className="source-pill">
              {reportSource === "backend" ? "Backend data" : "Sample data"}
            </span>
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
              <MetricCard label="Total Cameras" value={dailyReport.summary.total_cameras} />
              <MetricCard label="Road Segments" value={dailyReport.summary.total_road_segments} />
              <MetricCard label="Events Detected" value={dailyReport.summary.total_events_detected} />
              <MetricCard
                label="High Risk Segments"
                value={dailyReport.summary.high_risk_segments}
                danger
              />
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

            <ReportSection title="Executive Summary">
              <p className="long-report-text">
                {dailyReport.daily_report.executive_summary}
              </p>
            </ReportSection>

            <ReportSection title="Key Findings">
              <ul className="report-list">
                {dailyReport.daily_report.key_findings.map((finding) => (
                  <li key={finding}>{finding}</li>
                ))}
              </ul>
            </ReportSection>

            <ReportSection title="Recommended Admin Actions">
              <ul className="report-list">
                {dailyReport.daily_report.recommended_admin_actions.map(
                  (action) => (
                    <li key={action}>{action}</li>
                  )
                )}
              </ul>
            </ReportSection>

            <ReportSection title="Model Limitation Note">
              <p className="long-report-text">
                {dailyReport.daily_report.model_limitation_note}
              </p>
            </ReportSection>

            <ReportSection title="Segment Recommendations">
              <div className="recommendation-list">
                {dailyReport.hotspots.map((hotspot) => (
                  <div className="mini-card" key={hotspot.road_segment_id}>
                    <strong>{hotspot.location_name}</strong>
                    <span>{hotspot.recommendation.primary_intervention}</span>
                    <p>{hotspot.recommendation.explanation}</p>
                  </div>
                ))}
              </div>
            </ReportSection>
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

            <ReportSection title="Production Readiness">
              <p className="long-report-text">
                In production, this dashboard will read the latest generated
                daily report from the backend endpoint instead of static sample
                data. The intended flow is 24/7 CCTV sampling, detection, event
                storage, daily hotspot aggregation, LLM/RAG reporting, and
                dashboard display.
              </p>
            </ReportSection>
          </section>
        )}
      </main>
    </div>
  );
}

function LoginScreen() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(event) {
    event.preventDefault();
    setIsSubmitting(true);
    setError("");

    const { error: loginError } = await supabase.auth.signInWithPassword({
      email,
      password,
    });

    if (loginError) {
      setError(loginError.message);
    }

    setIsSubmitting(false);
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="brand login-brand">
          <div className="brand-icon">IG</div>
          <div>
            <h1>InfraGuard</h1>
            <p>Admin-only access</p>
          </div>
        </div>

        <h2>Admin Login</h2>
        <p className="login-note">
          Sign in with the admin account created in Supabase Auth.
        </p>

        <form onSubmit={handleSubmit} className="login-form">
          <label>
            Email
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              autoComplete="email"
              required
            />
          </label>

          <label>
            Password
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="current-password"
              required
            />
          </label>

          {error && <div className="login-error">{error}</div>}

          <button type="submit" disabled={isSubmitting}>
            {isSubmitting ? "Signing in..." : "Enter Dashboard"}
          </button>
        </form>
      </div>
    </div>
  );
}

function MetricCard({ label, value, danger = false }) {
  return (
    <div className={`metric-card ${danger ? "danger" : ""}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function ReportSection({ title, children }) {
  return (
    <div className="section">
      <h4>{title}</h4>
      {children}
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

      <ReportSection title="Incident Points">
        <p className="long-report-text">
          This hotspot contains {(hotspot.incidents || []).length} mapped
          incident points. Red dots on the map represent individual detected
          events, while the circle represents the hotspot area.
        </p>
      </ReportSection>

      <ReportSection title="Detected Event Types">
        <div className="tag-list">
          {hotspot.top_event_types.map((eventType) => (
            <span className="tag" key={eventType}>
              {eventType}
            </span>
          ))}
        </div>
      </ReportSection>

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