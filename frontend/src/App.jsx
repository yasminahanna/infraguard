import { useEffect, useMemo, useState } from "react";
import {
  Circle,
  CircleMarker,
  MapContainer,
  Marker,
  Popup,
  TileLayer,
} from "react-leaflet";
import L from "leaflet";
import {
  addCamera,
  analyzeCameraClip,
  getCameras,
  getIncidentEvidence,
  getLatestReport,
  getLiveFeed,
  getReportDetail,
  getReportHistory,
  submitFeedback,
  uploadCameraClip,
} from "./api";
import { supabase, supabaseConfigMissing } from "./supabaseClient";

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

function riskWeight(riskLevel) {
  if (riskLevel === "high") return 3;
  if (riskLevel === "medium") return 2;
  return 1;
}

function cameraIcon(riskLevel, status) {
  const color = hotspotColor(riskLevel);
  const offline = status && status !== "online";

  return L.divIcon({
    className: "camera-marker",
    html: `<div class="camera-pin ${offline ? "offline" : ""}" style="border-color:${color}">📷</div>`,
    iconSize: [34, 34],
    iconAnchor: [17, 17],
    popupAnchor: [0, -16],
  });
}

function formatDateTime(value) {
  if (!value) return "Not available";

  try {
    return new Intl.DateTimeFormat("en", {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(value));
  } catch {
    return value;
  }
}

function getAllIncidents(hotspots) {
  return hotspots.flatMap((hotspot) =>
    (hotspot.incidents || []).map((incident) => ({
      ...incident,
      road_segment_id: hotspot.road_segment_id,
      camera_id: hotspot.camera_id,
      location_name: hotspot.location_name,
      risk_level: hotspot.risk_level,
    }))
  );
}

function App() {
  const [session, setSession] = useState(null);
  const [authLoading, setAuthLoading] = useState(true);
  const [dailyReport, setDailyReport] = useState(null);
  const [reportSource, setReportSource] = useState("sample");
  const [activePage, setActivePage] = useState("overview");
  const [selectedSegmentId, setSelectedSegmentId] = useState(null);
  const [riskFilter, setRiskFilter] = useState("all");
  const [searchText, setSearchText] = useState("");
  const [sortMode, setSortMode] = useState("risk");
  const [selectedIncident, setSelectedIncident] = useState(null);
  const [selectedEvidence, setSelectedEvidence] = useState(null);
  const [evidenceLoading, setEvidenceLoading] = useState(false);
  const [evidenceError, setEvidenceError] = useState("");
  const [liveFeed, setLiveFeed] = useState(null);
  const [cameras, setCameras] = useState([]);
  const [selectedCamera, setSelectedCamera] = useState(null);
  const [reportHistory, setReportHistory] = useState([]);
  const [showAddCamera, setShowAddCamera] = useState(false);
  const [openReport, setOpenReport] = useState(null);

  useEffect(() => {
    if (supabaseConfigMissing || !supabase) {
      setAuthLoading(false);
      return;
    }

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

    getLatestReport(session.access_token).then(({ report, source }) => {
      setDailyReport(report);
      setReportSource(source);

      if (report.hotspots?.length > 0) {
        setSelectedSegmentId(report.hotspots[0].road_segment_id);
      }
    });
  }, [session]);

  useEffect(() => {
    if (!session) return;

    getCameras(session.access_token).then(setCameras);
    getReportHistory(session.access_token).then(setReportHistory);
  }, [session]);

  useEffect(() => {
    if (!session) return;

    let active = true;
    const poll = () => {
      getLiveFeed(session.access_token).then((feed) => {
        if (active) setLiveFeed(feed);
      });
    };

    poll();
    const timer = setInterval(poll, 15000);

    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [session]);

  const filteredHotspots = useMemo(() => {
    if (!dailyReport) return [];

    const query = searchText.trim().toLowerCase();

    const filtered = dailyReport.hotspots.filter((hotspot) => {
      const riskMatches =
        riskFilter === "all" || hotspot.risk_level === riskFilter;

      const searchableText = [
        hotspot.road_segment_id,
        hotspot.camera_id,
        hotspot.location_name,
        hotspot.risk_level,
        hotspot.trend,
        hotspot.recommendation?.primary_intervention,
        ...(hotspot.top_event_types || []),
      ]
        .join(" ")
        .toLowerCase();

      const searchMatches = !query || searchableText.includes(query);

      return riskMatches && searchMatches;
    });

    return [...filtered].sort((a, b) => {
      if (sortMode === "score") return b.hotspot_score - a.hotspot_score;
      if (sortMode === "events") return b.event_count - a.event_count;
      if (sortMode === "name") {
        return a.location_name.localeCompare(b.location_name);
      }

      return riskWeight(b.risk_level) - riskWeight(a.risk_level);
    });
  }, [dailyReport, riskFilter, searchText, sortMode]);

  const allIncidents = useMemo(() => {
    if (!dailyReport) return [];

    return getAllIncidents(filteredHotspots).sort(
      (a, b) => new Date(b.timestamp) - new Date(a.timestamp)
    );
  }, [dailyReport, filteredHotspots]);

  const cameraById = useMemo(() => {
    const lookup = {};
    for (const camera of cameras) {
      lookup[camera.camera_id] = camera;
    }
    return lookup;
  }, [cameras]);

  function openCameraFootage(cameraInfo) {
    const enriched = cameraById[cameraInfo.camera_id] || {};
    setSelectedCamera({ ...cameraInfo, ...enriched });
  }

  function closeCameraFootage() {
    setSelectedCamera(null);
  }

  async function openReportDetail(reportId) {
    setOpenReport({ loading: true });
    try {
      const report = await getReportDetail(session.access_token, reportId);
      setOpenReport({ loading: false, report });
    } catch {
      setOpenReport({ loading: false, error: "Could not load this report." });
    }
  }

  async function refreshDashboard() {
    const token = session.access_token;
    const [{ report, source }, cams, history] = await Promise.all([
      getLatestReport(token),
      getCameras(token),
      getReportHistory(token),
    ]);
    setDailyReport(report);
    setReportSource(source);
    setCameras(cams);
    setReportHistory(history);
    if (report.hotspots?.length > 0) {
      setSelectedSegmentId(report.hotspots[0].road_segment_id);
    }
  }

  async function handleLogout() {
    await supabase.auth.signOut();
    setDailyReport(null);
    setSelectedSegmentId(null);
  }

  async function openIncidentEvidence(incident) {
    setSelectedIncident(incident);
    setSelectedEvidence(null);
    setEvidenceError("");
    setEvidenceLoading(true);

    try {
      const evidence = await getIncidentEvidence(
        session.access_token,
        incident.incident_id
      );

      setSelectedEvidence(evidence);
    } catch {
      setEvidenceError(
        "Could not load CCTV evidence from the backend for this incident."
      );
    } finally {
      setEvidenceLoading(false);
    }
  }

  function closeIncidentEvidence() {
    setSelectedIncident(null);
    setSelectedEvidence(null);
    setEvidenceError("");
  }

  async function handleSubmitFeedback(payload) {
    return submitFeedback(session.access_token, {
      ...payload,
      report_id: dailyReport?.report_id || "unknown",
      admin_email: session?.user?.email || null,
    });
  }

  if (supabaseConfigMissing) {
    return (
      <div className="loading-screen">
        Supabase configuration is missing. Check VITE_SUPABASE_URL and
        VITE_SUPABASE_ANON_KEY.
      </div>
    );
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
            className={`nav-item ${activePage === "archives" ? "active" : ""}`}
            onClick={() => setActivePage("archives")}
          >
            Archives
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
        <header className="top-header">
          <div className="top-header-left">
            <button className="menu-button">☰</button>
            <div>
              <p className="eyebrow">Daily CCTV Safety Report</p>
              <h2>
                {dailyReport.city}, {dailyReport.country}
              </h2>
            </div>
          </div>

          <div className="top-header-actions">
            <span className="live-dot"></span>
            <span>Monitoring active</span>
            <span className="source-pill">
              {reportSource === "backend" ? "Backend data" : "Sample data"}
            </span>
          </div>
        </header>

        <section className="welcome-row">
          <div>
            <h3>Hi, Admin</h3>
            <p>
              Generated at {formatDateTime(dailyReport.generated_at)} · Review
              current hotspot risk, incidents, and recommendations.
            </p>
          </div>
          <div className="quick-search">
            <input
              value={searchText}
              onChange={(event) => setSearchText(event.target.value)}
              placeholder="Search segment, location, event..."
            />
          </div>
        </section>

        <ReportStatusBar dailyReport={dailyReport} reportSource={reportSource} />

        {!dailyReport.recommender_status.using_llm_api && (
          <div className="warning-box top-warning">
            <strong>LLM API not connected</strong>
            <p>{dailyReport.recommender_status.warning}</p>
          </div>
        )}

        {(activePage === "overview" || activePage === "hotspots") && (
          <DashboardControls
            riskFilter={riskFilter}
            setRiskFilter={setRiskFilter}
            sortMode={sortMode}
            setSortMode={setSortMode}
          />
        )}

        {activePage === "overview" && (
          <>
            <section className="summary-grid">
              <MetricCard
                label="Total Cameras"
                value={dailyReport.summary.total_cameras}
              />
              <MetricCard
                label="Road Segments"
                value={dailyReport.summary.total_road_segments}
              />
              <MetricCard
                label="Events Detected"
                value={dailyReport.summary.total_events_detected}
              />
              <MetricCard
                label="High Risk Segments"
                value={dailyReport.summary.high_risk_segments}
                danger
              />
            </section>

            <section className="content-grid">
              <MapPanel
                hotspots={filteredHotspots}
                setSelectedSegmentId={setSelectedSegmentId}
                openIncidentEvidence={openIncidentEvidence}
                openCameraFootage={openCameraFootage}
                cameraById={cameraById}
                onAddCamera={() => setShowAddCamera(true)}
              />

              <div className="side-stack">
                <LiveFeedPanel liveFeed={liveFeed} />
                <HotspotDetails
                  hotspot={selectedHotspot}
                  onSubmitFeedback={handleSubmitFeedback}
                />
                <IncidentFeed
                  incidents={allIncidents}
                  setSelectedSegmentId={setSelectedSegmentId}
                  openIncidentEvidence={openIncidentEvidence}
                />
              </div>
            </section>

            <section className="panel table-panel">
              <div className="panel-header">
                <div>
                  <h3>Daily Hotspot Ranking</h3>
                  <p>
                    Showing {filteredHotspots.length} of{" "}
                    {dailyReport.hotspots.length} monitored road segments.
                  </p>
                </div>
              </div>

              <HotspotTable
                hotspots={filteredHotspots}
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
                <p>
                  Search, sort, and inspect monitored road segments by risk.
                </p>
              </div>
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
                  <strong>Start:</strong>{" "}
                  {formatDateTime(dailyReport.report_window.start)}
                </p>
                <p>
                  <strong>End:</strong>{" "}
                  {formatDateTime(dailyReport.report_window.end)}
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

        {activePage === "archives" && (
          <ArchivesPanel reports={reportHistory} onOpen={openReportDetail} />
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
              <HealthCard service="Recommender IEP" status="Online" />
            </div>

            <ReportSection title="Production Readiness">
              <p className="long-report-text">
                In production, this dashboard reads the latest generated daily
                report from the backend endpoint. The intended flow is 24/7 CCTV
                sampling, detection, event storage, daily hotspot aggregation,
                LLM/RAG reporting, feedback-conditioned regeneration, and
                dashboard display.
              </p>
            </ReportSection>
          </section>
        )}

        <EvidenceReviewPanel
          incident={selectedIncident}
          evidence={selectedEvidence}
          isLoading={evidenceLoading}
          error={evidenceError}
          onClose={closeIncidentEvidence}
        />

        <CameraFootagePanel
          key={selectedCamera?.camera_id}
          camera={selectedCamera}
          onClose={closeCameraFootage}
        />

        {showAddCamera && (
          <AddCameraModal
            accessToken={session.access_token}
            onClose={() => setShowAddCamera(false)}
            onComplete={refreshDashboard}
          />
        )}

        {openReport && (
          <ReportDetailModal state={openReport} onClose={() => setOpenReport(null)} />
        )}
      </main>
    </div>
  );
}

function ReportStatusBar({ dailyReport, reportSource }) {
  const usingLlm = dailyReport.recommender_status?.using_llm_api;

  return (
    <section className="status-strip">
      <div>
        <span>Report Source</span>
        <strong>
          {reportSource === "backend" ? "Backend generated" : "Sample fallback"}
        </strong>
      </div>
      <div>
        <span>Recommendation Mode</span>
        <strong>{usingLlm ? "LLM enabled" : "Fallback mode"}</strong>
      </div>
      <div>
        <span>Generated</span>
        <strong>{formatDateTime(dailyReport.generated_at)}</strong>
      </div>
      <div>
        <span>Report Window</span>
        <strong>
          {formatDateTime(dailyReport.report_window.start)} →{" "}
          {formatDateTime(dailyReport.report_window.end)}
        </strong>
      </div>
    </section>
  );
}

function DashboardControls({ riskFilter, setRiskFilter, sortMode, setSortMode }) {
  return (
    <section className="dashboard-controls">
      <label>
        Risk
        <select
          value={riskFilter}
          onChange={(event) => setRiskFilter(event.target.value)}
        >
          <option value="all">All risks</option>
          <option value="high">High only</option>
          <option value="medium">Medium only</option>
          <option value="low">Low only</option>
        </select>
      </label>

      <label>
        Sort
        <select
          value={sortMode}
          onChange={(event) => setSortMode(event.target.value)}
        >
          <option value="risk">Risk level</option>
          <option value="score">Hotspot score</option>
          <option value="events">Event count</option>
          <option value="name">Location name</option>
        </select>
      </label>
    </section>
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

function MapPanel({
  hotspots,
  setSelectedSegmentId,
  openIncidentEvidence,
  openCameraFootage,
  cameraById,
  onAddCamera,
}) {
  return (
    <div className="map-panel panel">
      <div className="panel-header">
        <div>
          <h3>City CCTV &amp; Hotspot Map</h3>
          <p>
            📷 Camera markers are live CCTV sources — click one for its footage and
            device info. Red dots are detected incidents.
          </p>
        </div>
        <button className="add-camera-btn" onClick={onAddCamera}>
          + Add CCTV
        </button>
      </div>

      <MapContainer center={[13.7563, 100.5018]} zoom={13} className="map">
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

              {(() => {
                const camera = cameraById[hotspot.camera_id] || {};
                const cameraInfo = {
                  camera_id: hotspot.camera_id,
                  road_segment_id: hotspot.road_segment_id,
                  location_name: camera.location_name || hotspot.location_name,
                  risk_level: hotspot.risk_level,
                };

                return (
                  <Marker
                    position={[hotspot.location.lat, hotspot.location.lon]}
                    icon={cameraIcon(hotspot.risk_level, camera.status)}
                    eventHandlers={{
                      click: () => setSelectedSegmentId(hotspot.road_segment_id),
                    }}
                  >
                    <Popup>
                      <strong>📷 {camera.location_name || hotspot.location_name}</strong>
                      <br />
                      Camera: {hotspot.camera_id}
                      <br />
                      IP: {camera.ip_address || "n/a"}
                      <br />
                      Status: {camera.status || "unknown"} · Risk: {hotspot.risk_level}
                      <br />
                      <button
                        type="button"
                        className="popup-cam-btn"
                        onClick={() => openCameraFootage(cameraInfo)}
                      >
                        ▶ Watch camera footage
                      </button>
                    </Popup>
                  </Marker>
                );
              })()}

              {(hotspot.incidents || []).map((incident) => (
                <CircleMarker
                  key={incident.incident_id}
                  center={[incident.lat, incident.lon]}
                  radius={8}
                  pathOptions={{
                    color: "#991b1b",
                    fillColor: "#ef4444",
                    fillOpacity: 0.95,
                    weight: 2,
                  }}
                  eventHandlers={{
                    click: () => {
                      setSelectedSegmentId(hotspot.road_segment_id);
                      openIncidentEvidence({
                        ...incident,
                        road_segment_id: hotspot.road_segment_id,
                        camera_id: hotspot.camera_id,
                        location_name: hotspot.location_name,
                        risk_level: hotspot.risk_level,
                      });
                    },
                  }}
                >
                  <Popup>
                    <strong>{incident.event_type}</strong>
                    <br />
                    Severity: {incident.severity}
                    <br />
                    Confidence: {incident.confidence}
                    <br />
                    Time: {formatDateTime(incident.timestamp)}
                    <br />
                    Click dot to review CCTV evidence.
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

function LiveFeedPanel({ liveFeed }) {
  const isLive = liveFeed && liveFeed.status === "live";

  return (
    <div className="panel live-panel">
      <div className="panel-header">
        <div>
          <h3>
            <span className={`live-dot ${isLive ? "on" : ""}`} /> Live CCTV Feed
          </h3>
          <p>
            {isLive
              ? `Camera ${liveFeed.camera_id || ""} · updated ${formatDateTime(
                  liveFeed.updated_at
                )}`
              : "Waiting for the live stream ingestor..."}
          </p>
        </div>
      </div>

      {isLive ? (
        <>
          <div className="live-metrics">
            <div>
              <span>Vehicles</span>
              <strong>{liveFeed.vehicle_count ?? "—"}</strong>
            </div>
            <div>
              <span>Risk</span>
              <strong>{liveFeed.hotspot?.risk_level || "—"}</strong>
            </div>
          </div>
          <div className="live-events">
            {(liveFeed.events || []).length === 0 ? (
              <span className="tag">no events this frame</span>
            ) : (
              (liveFeed.events || []).map((event, index) => (
                <span className="tag" key={index}>
                  {event.event_type} ({event.severity})
                </span>
              ))
            )}
          </div>
        </>
      ) : (
        <p className="long-report-text">
          {liveFeed?.message ||
            "The live CCTV ingestor analyzes sampled frames in real time. Results appear here once it is running."}
        </p>
      )}
    </div>
  );
}

function HotspotDetails({ hotspot, onSubmitFeedback }) {
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
          <span className="provider-pill">
            {hotspot.recommendation.provider}
          </span>
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

      <FeedbackControls
        key={hotspot.road_segment_id}
        hotspot={hotspot}
        onSubmitFeedback={onSubmitFeedback}
      />
    </div>
  );
}

function FeedbackControls({ hotspot, onSubmitFeedback }) {
  const [verdict, setVerdict] = useState(null);
  const [corrected, setCorrected] = useState("");
  const [note, setNote] = useState("");
  const [status, setStatus] = useState("idle");

  async function submit() {
    if (!verdict || !onSubmitFeedback) return;
    setStatus("sending");
    try {
      await onSubmitFeedback({
        road_segment_id: hotspot.road_segment_id,
        verdict,
        corrected_intervention: corrected.trim() || null,
        note: note.trim() || null,
      });
      setStatus("sent");
    } catch {
      setStatus("error");
    }
  }

  return (
    <div className="section feedback-box">
      <h4>Admin Feedback</h4>
      <p className="feedback-hint">
        Was this recommendation correct? Your feedback conditions the next report.
      </p>

      <div className="feedback-actions">
        <button
          type="button"
          className={`feedback-btn approve ${verdict === "accept" ? "active" : ""}`}
          onClick={() => setVerdict("accept")}
        >
          👍 Accept
        </button>
        <button
          type="button"
          className={`feedback-btn reject ${verdict === "reject" ? "active" : ""}`}
          onClick={() => setVerdict("reject")}
        >
          👎 Reject
        </button>
      </div>

      <input
        className="feedback-input"
        placeholder="Corrected intervention (optional)"
        value={corrected}
        onChange={(event) => setCorrected(event.target.value)}
      />
      <textarea
        className="feedback-input"
        placeholder="Note (optional)"
        rows={2}
        value={note}
        onChange={(event) => setNote(event.target.value)}
      />

      <button
        type="button"
        className="feedback-submit"
        onClick={submit}
        disabled={!verdict || status === "sending"}
      >
        {status === "sending" ? "Submitting..." : "Submit feedback"}
      </button>

      {status === "sent" && (
        <p className="feedback-status ok">✓ Feedback recorded — thank you.</p>
      )}
      {status === "error" && (
        <p className="feedback-status err">Could not submit feedback. Try again.</p>
      )}
    </div>
  );
}

function IncidentFeed({ incidents, setSelectedSegmentId, openIncidentEvidence }) {
  return (
    <div className="panel incident-feed">
      <div className="panel-header">
        <div>
          <h3>Active Incidents</h3>
          <p>Most recent incidents from the filtered hotspot set.</p>
        </div>
      </div>

      <div className="incident-list">
        {incidents.slice(0, 8).map((incident) => (
          <button
            className="incident-item"
            key={incident.incident_id}
            onClick={() => {
              setSelectedSegmentId(incident.road_segment_id);
              openIncidentEvidence(incident);
            }}
          >
            <span className={`incident-dot ${riskClass(incident.risk_level)}`}></span>
            <div>
              <strong>{incident.event_type}</strong>
              <p>
                {incident.location_name} · {formatDateTime(incident.timestamp)}
              </p>
            </div>
          </button>
        ))}

        {incidents.length === 0 && (
          <p className="long-report-text">No incidents match the current filters.</p>
        )}
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

      {hotspots.length === 0 && (
        <div className="empty-state">No hotspots match the current filters.</div>
      )}
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

function EvidenceReviewPanel({ incident, evidence, isLoading, error, onClose }) {
  if (!incident) return null;

  const evidenceInfo = evidence?.evidence;
  const decisionContext = evidence?.decision_context;

  return (
    <div className="evidence-overlay">
      <aside className="evidence-panel">
        <div className="evidence-header">
          <div>
            <span>CCTV Evidence Review</span>
            <h3>{incident.event_type}</h3>
          </div>

          <button onClick={onClose}>Close</button>
        </div>

        {isLoading && (
          <div className="evidence-loading">
            Loading incident evidence from backend...
          </div>
        )}

        {error && <div className="evidence-error">{error}</div>}

        {!isLoading && !error && (
          <>
            <div className="evidence-video-box">
              {evidenceInfo?.clip_url ? (
                <video controls src={evidenceInfo.clip_url}>
                  Your browser does not support video playback.
                </video>
              ) : (
                <div className="evidence-placeholder">
                  <strong>No CCTV clip attached yet</strong>
                  <p>
                    The backend evidence endpoint is working, but this incident
                    does not yet have a real video clip URL. When live CCTV
                    storage is connected, the clip will appear here.
                  </p>
                </div>
              )}
            </div>

            <div className="evidence-grid">
              <div>
                <span>Incident ID</span>
                <strong>{incident.incident_id}</strong>
              </div>

              <div>
                <span>Severity</span>
                <strong>{incident.severity}</strong>
              </div>

              <div>
                <span>Confidence</span>
                <strong>{incident.confidence}</strong>
              </div>

              <div>
                <span>Timestamp</span>
                <strong>{formatDateTime(incident.timestamp)}</strong>
              </div>

              <div>
                <span>Location</span>
                <strong>
                  {decisionContext?.location_name ||
                    incident.location_name ||
                    "—"}
                </strong>
              </div>

              <div>
                <span>Camera</span>
                <strong>{decisionContext?.camera_id || incident.camera_id}</strong>
              </div>

              <div>
                <span>Road Segment</span>
                <strong>
                  {decisionContext?.road_segment_id || incident.road_segment_id}
                </strong>
              </div>
            </div>

            <div className="evidence-section">
              <h4>Why this incident was flagged</h4>
              <p>
                {decisionContext?.explanation ||
                  "This incident was included because it matched a detected traffic-risk event in the latest report."}
              </p>
            </div>

            <div className="evidence-section">
              <h4>Evidence status</h4>
              <p>
                {evidenceInfo?.clip_available
                  ? "A CCTV evidence clip is available for review."
                  : "Only event metadata is currently available. CCTV clip storage is ready to be connected."}
              </p>
            </div>
          </>
        )}
      </aside>
    </div>
  );
}

function ArchivesPanel({ reports, onOpen }) {
  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <h3>Report Archives</h3>
          <p>One report per day, newest first. Click a report to open it in full.</p>
        </div>
        <span className="source-pill">{reports.length} archived</span>
      </div>

      {reports.length === 0 ? (
        <p className="long-report-text">
          No archived reports yet. Each generated daily report is stored here so you
          can review past CCTV monitoring windows.
        </p>
      ) : (
        <div className="archive-list">
          {reports.map((report, index) => (
            <button
              type="button"
              className="mini-card archive-card"
              key={`${report.report_id}-${index}`}
              onClick={() => onOpen(report.report_id)}
            >
              <div className="archive-card-head">
                <strong>{report.report_id}</strong>
                <span
                  className={`risk-pill small ${
                    report.using_llm_api ? "risk-low" : "risk-medium"
                  }`}
                >
                  {report.using_llm_api ? "LLM" : "Fallback"}
                </span>
              </div>

              <span className="archive-meta">
                {formatDateTime(report.generated_at)} · {report.city}
                {report.country ? `, ${report.country}` : ""}
              </span>

              <div className="archive-stats">
                <span>{report.summary?.total_events_detected ?? "—"} events</span>
                <span>{report.summary?.high_risk_segments ?? "—"} high risk</span>
                <span>{report.hotspot_count} segments</span>
              </div>

              {report.executive_summary && (
                <p className="archive-summary">{report.executive_summary}</p>
              )}

              <span className="archive-open">Open full report →</span>
            </button>
          ))}
        </div>
      )}
    </section>
  );
}

function ReportDetailModal({ state, onClose }) {
  const report = state.report;
  const daily = report?.daily_report;

  return (
    <div className="evidence-overlay">
      <aside className="evidence-panel report-detail">
        <div className="evidence-header">
          <div>
            <span>Daily Report</span>
            <h3>{report ? report.report_id : "Loading..."}</h3>
          </div>
          <button onClick={onClose}>Close</button>
        </div>

        {state.loading && <div className="evidence-loading">Loading report...</div>}
        {state.error && <div className="evidence-error">{state.error}</div>}

        {report && (
          <>
            <span className="archive-meta">
              {formatDateTime(report.generated_at)} · {report.city}
              {report.country ? `, ${report.country}` : ""} ·{" "}
              {report.recommender_status?.using_llm_api ? "LLM" : "Fallback"}
            </span>

            <div className="report-grid">
              <div className="mini-card">
                <h4>Report Window</h4>
                <p>
                  <strong>Start:</strong>{" "}
                  {formatDateTime(report.report_window?.start)}
                </p>
                <p>
                  <strong>End:</strong> {formatDateTime(report.report_window?.end)}
                </p>
              </div>
              <div className="mini-card">
                <h4>City Summary</h4>
                <p>Total events: {report.summary?.total_events_detected}</p>
                <p>High risk: {report.summary?.high_risk_segments}</p>
                <p>Medium risk: {report.summary?.medium_risk_segments}</p>
                <p>Low risk: {report.summary?.low_risk_segments}</p>
              </div>
            </div>

            {daily?.executive_summary && (
              <ReportSection title="Executive Summary">
                <p className="long-report-text">{daily.executive_summary}</p>
              </ReportSection>
            )}

            {daily?.key_findings?.length > 0 && (
              <ReportSection title="Key Findings">
                <ul className="report-list">
                  {daily.key_findings.map((f) => (
                    <li key={f}>{f}</li>
                  ))}
                </ul>
              </ReportSection>
            )}

            {daily?.recommended_admin_actions?.length > 0 && (
              <ReportSection title="Recommended Admin Actions">
                <ul className="report-list">
                  {daily.recommended_admin_actions.map((a) => (
                    <li key={a}>{a}</li>
                  ))}
                </ul>
              </ReportSection>
            )}

            <ReportSection title="Segment Recommendations">
              <div className="recommendation-list">
                {(report.hotspots || []).map((h) => (
                  <div className="mini-card" key={h.road_segment_id}>
                    <strong>{h.location_name}</strong>
                    <span>{h.recommendation?.primary_intervention}</span>
                    <p>{h.recommendation?.explanation}</p>
                  </div>
                ))}
              </div>
            </ReportSection>
          </>
        )}
      </aside>
    </div>
  );
}

function AddCameraModal({ accessToken, onClose, onComplete }) {
  const [form, setForm] = useState({
    camera_id: "",
    display_name: "",
    ip_address: "",
    model: "",
    road_segment_id: "",
    location_name: "",
    lat: "33.8938",
    lon: "35.5018",
  });
  const [file, setFile] = useState(null);
  const [step, setStep] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  function update(field, value) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  async function submit(event) {
    event.preventDefault();
    setError("");

    if (!form.camera_id.trim()) return setError("Camera ID is required.");
    if (!file) return setError("Please choose a video clip to upload.");

    const cameraId = form.camera_id.trim();
    const segment = form.road_segment_id.trim() || `segment_${cameraId}`;
    const camera = {
      camera_id: cameraId,
      display_name: form.display_name.trim() || cameraId,
      ip_address: form.ip_address.trim() || null,
      model: form.model.trim() || null,
      status: "online",
      road_segment_id: segment,
      location_name: form.location_name.trim() || form.display_name.trim() || cameraId,
      lat: parseFloat(form.lat),
      lon: parseFloat(form.lon),
    };

    setBusy(true);
    try {
      setStep("Registering camera...");
      await addCamera(accessToken, camera);

      setStep("Uploading video clip...");
      await uploadCameraClip(accessToken, cameraId, file);

      setStep("Running detection + regenerating report (this can take a moment)...");
      const result = await analyzeCameraClip(accessToken, cameraId);

      setStep("Refreshing dashboard...");
      await onComplete();

      const a = result?.result?.analysis;
      setStep(
        a
          ? `Done — analyzed ${a.frames_analyzed} frames, ${a.events_detected} events, ${a.vehicle_count} vehicles.`
          : "Done."
      );
      setTimeout(onClose, 1200);
    } catch (err) {
      setError(err.message || "Something went wrong while onboarding the camera.");
      setStep("");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="evidence-overlay">
      <aside className="evidence-panel">
        <div className="evidence-header">
          <div>
            <span>Onboard CCTV</span>
            <h3>Add a Camera</h3>
          </div>
          <button onClick={onClose} disabled={busy}>
            Close
          </button>
        </div>

        <p className="long-report-text">
          Register a CCTV source and upload a clip. The detection model (YOLO + CLIP)
          analyzes it and regenerates the report, so the camera appears on the map with
          real incidents.
        </p>

        <form className="add-camera-form" onSubmit={submit}>
          <label>
            Camera ID *
            <input
              value={form.camera_id}
              onChange={(e) => update("camera_id", e.target.value)}
              placeholder="e.g. hamra_03"
            />
          </label>
          <label>
            Display name
            <input
              value={form.display_name}
              onChange={(e) => update("display_name", e.target.value)}
              placeholder="e.g. Hamra Street West"
            />
          </label>
          <div className="form-row">
            <label>
              IP address
              <input
                value={form.ip_address}
                onChange={(e) => update("ip_address", e.target.value)}
                placeholder="10.20.14.xx"
              />
            </label>
            <label>
              Model
              <input
                value={form.model}
                onChange={(e) => update("model", e.target.value)}
                placeholder="Hikvision DS-..."
              />
            </label>
          </div>
          <div className="form-row">
            <label>
              Latitude
              <input value={form.lat} onChange={(e) => update("lat", e.target.value)} />
            </label>
            <label>
              Longitude
              <input value={form.lon} onChange={(e) => update("lon", e.target.value)} />
            </label>
          </div>
          <label>
            Road segment ID
            <input
              value={form.road_segment_id}
              onChange={(e) => update("road_segment_id", e.target.value)}
              placeholder="auto: segment_<camera id>"
            />
          </label>
          <label>
            Video clip *
            <input
              type="file"
              accept="video/mp4,video/*"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
            />
          </label>

          {error && <div className="login-error">{error}</div>}
          {step && <div className="add-camera-step">{step}</div>}

          <button type="submit" className="feedback-submit" disabled={busy}>
            {busy ? "Working..." : "Add camera & analyze"}
          </button>
        </form>
      </aside>
    </div>
  );
}

function CameraFootagePanel({ camera, onClose }) {
  const [videoFailed, setVideoFailed] = useState(false);

  if (!camera) return null;

  const offline = camera.status && camera.status !== "online";
  const showVideo = camera.clip_url && !videoFailed;

  return (
    <div className="evidence-overlay">
      <aside className="evidence-panel">
        <div className="evidence-header">
          <div>
            <span>CCTV Camera Feed</span>
            <h3>📷 {camera.location_name || camera.camera_id}</h3>
          </div>

          <button onClick={onClose}>Close</button>
        </div>

        <div className="evidence-video-box">
          {showVideo ? (
            <video
              controls
              autoPlay
              muted
              src={camera.clip_url}
              onError={() => setVideoFailed(true)}
            >
              Your browser does not support video playback.
            </video>
          ) : (
            <div className="evidence-placeholder">
              <strong>
                {offline ? "Camera feed unavailable" : "No footage connected"}
              </strong>
              <p>
                {videoFailed
                  ? "The footage URL is set but the clip could not be loaded. Confirm the clip is uploaded to the Azure Blob container."
                  : offline
                  ? `This camera is currently reporting status "${camera.status}", so no live footage is available.`
                  : "This camera is registered and mapped, but no footage clip is attached yet."}
              </p>
            </div>
          )}
        </div>

        <div className="evidence-grid">
          <div>
            <span>Camera ID</span>
            <strong>{camera.camera_id}</strong>
          </div>

          <div>
            <span>IP Address</span>
            <strong>{camera.ip_address || "n/a"}</strong>
          </div>

          <div>
            <span>Status</span>
            <strong>{camera.status || "unknown"}</strong>
          </div>

          <div>
            <span>Model</span>
            <strong>{camera.model || "n/a"}</strong>
          </div>

          <div>
            <span>Resolution</span>
            <strong>
              {camera.resolution || "n/a"}
              {camera.fps ? ` · ${camera.fps}fps` : ""}
            </strong>
          </div>

          <div>
            <span>Road Segment</span>
            <strong>{camera.road_segment_id || "n/a"}</strong>
          </div>

          <div>
            <span>Location</span>
            <strong>{camera.location_name || "n/a"}</strong>
          </div>

          <div>
            <span>Installed</span>
            <strong>{camera.installed_on || "n/a"}</strong>
          </div>
        </div>

        {camera.rtsp_url && (
          <div className="evidence-section">
            <h4>Stream endpoint</h4>
            <p className="camera-rtsp">{camera.rtsp_url}</p>
          </div>
        )}

        <div className="evidence-section">
          <h4>About this feed</h4>
          <p>
            Recorded CCTV footage sampled by the detection pipeline for this monitoring
            location. The red dots on the map are individual incidents this camera
            detected.
          </p>
        </div>
      </aside>
    </div>
  );
}

export default App;