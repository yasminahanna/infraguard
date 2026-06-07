import fallbackReport from "./daily_report_sample.json";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

function buildAuthHeaders(accessToken) {
  const headers = {};

  if (accessToken) {
    headers.Authorization = `Bearer ${accessToken}`;
  }

  return headers;
}

export async function getLatestReport(accessToken) {
  try {
    const response = await fetch(`${API_BASE_URL}/v1/reports/latest`, {
      headers: buildAuthHeaders(accessToken),
    });

    if (!response.ok) {
      throw new Error("Failed to fetch latest report.");
    }

    const data = await response.json();

    if (data.status === "placeholder") {
      return {
        report: fallbackReport,
        source: "sample",
      };
    }

    return {
      report: data,
      source: "backend",
    };
  } catch {
    return {
      report: fallbackReport,
      source: "sample",
    };
  }
}

export async function getIncidentEvidence(accessToken, incidentId) {
  const response = await fetch(`${API_BASE_URL}/v1/evidence/${incidentId}`, {
    headers: buildAuthHeaders(accessToken),
  });

  if (!response.ok) {
    throw new Error("Failed to load incident evidence.");
  }

  return response.json();
}