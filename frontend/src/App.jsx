import { MapContainer, TileLayer, Marker, Popup } from "react-leaflet";
import dailyReport from "../../samples/daily_report_sample.json";

function riskClass(riskLevel) {
  if (riskLevel === "high") return "risk-high";
  if (riskLevel === "medium") return "risk-medium";
  return "risk-low";
}

function App() {
  const hotspots = dailyReport.hotspots;
  const mainHotspot = hotspots[0];

  return (
    <div className="page">
      <header className="header">
        <div>
          <h1>InfraGuard Admin Dashboard</h1>
          <p>
            Daily road safety report for {dailyReport.city}, {dailyReport.country}
          </p>
        </div>
        <div className="status-card">
          <strong>Generated</strong>
          <span>{dailyReport.generated_at}</span>
        </div>
      </header>

      <section className="summary-grid">
        <div className="card">
          <span>Total Cameras</span>
          <strong>{dailyReport.summary.total_cameras}</strong>
        </div>
        <div className="card">
          <span>Total Events</span>
          <strong>{dailyReport.summary.total_events_detected}</strong>
        </div>
        <div className="card">
          <span>High Risk Segments</span>
          <strong>{dailyReport.summary.high_risk_segments}</strong>
        </div>
        <div className="card">
          <span>Medium Risk Segments</span>
          <strong>{dailyReport.summary.medium_risk_segments}</strong>
        </div>
      </section>

      <main className="main-grid">
        <section className="panel">
          <h2>City Hotspot Map</h2>

          <MapContainer
            center={[33.8955, 35.486]}
            zoom={14}
            className="map"
          >
            <TileLayer
              attribution="&copy; OpenStreetMap contributors"
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />

            {hotspots.map((hotspot) => (
              <Marker
                key={hotspot.road_segment_id}
                position={[hotspot.location.lat, hotspot.location.lon]}
              >
                <Popup>
                  <strong>{hotspot.location_name}</strong>
                  <br />
                  Risk: {hotspot.risk_level}
                  <br />
                  Score: {hotspot.hotspot_score}
                </Popup>
              </Marker>
            ))}
          </MapContainer>
        </section>

        <section className="panel">
          <h2>Highest Priority Hotspot</h2>

          <div className={`risk-badge ${riskClass(mainHotspot.risk_level)}`}>
            {mainHotspot.risk_level.toUpperCase()} RISK
          </div>

          <h3>{mainHotspot.location_name}</h3>

          <p>
            <strong>Road segment:</strong> {mainHotspot.road_segment_id}
          </p>
          <p>
            <strong>Hotspot score:</strong> {mainHotspot.hotspot_score}
          </p>
          <p>
            <strong>Trend:</strong> {mainHotspot.trend}
          </p>
          <p>
            <strong>Events detected:</strong> {mainHotspot.event_count}
          </p>

          <h3>Top Event Types</h3>
          <ul>
            {mainHotspot.top_event_types.map((eventType) => (
              <li key={eventType}>{eventType}</li>
            ))}
          </ul>

          <h3>Recommendation</h3>
          <p>
            <strong>Primary intervention:</strong>{" "}
            {mainHotspot.recommendation.primary_intervention}
          </p>
          <p>
            <strong>Priority:</strong> {mainHotspot.recommendation.priority}
          </p>
          <p>{mainHotspot.recommendation.explanation}</p>
        </section>
      </main>
    </div>
  );
}

export default App;