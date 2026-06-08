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

export async function getCameras(accessToken) {
  try {
    const response = await fetch(`${API_BASE_URL}/v1/cameras`, {
      headers: buildAuthHeaders(accessToken),
    });

    if (!response.ok) {
      throw new Error("Failed to fetch cameras.");
    }

    const data = await response.json();
    return data.cameras || [];
  } catch {
    return [];
  }
}

export async function getReportHistory(accessToken) {
  try {
    const response = await fetch(`${API_BASE_URL}/v1/reports/history`, {
      headers: buildAuthHeaders(accessToken),
    });

    if (!response.ok) {
      throw new Error("Failed to fetch report history.");
    }

    const data = await response.json();
    return data.reports || [];
  } catch {
    return [];
  }
}

export async function getReportDetail(accessToken, reportId) {
  const response = await fetch(
    `${API_BASE_URL}/v1/reports/history/${encodeURIComponent(reportId)}`,
    { headers: buildAuthHeaders(accessToken) }
  );

  if (!response.ok) {
    throw new Error("Failed to load report.");
  }

  const data = await response.json();
  return data.report;
}

export async function getLiveFeed(accessToken) {
  try {
    const response = await fetch(`${API_BASE_URL}/v1/live`, {
      headers: buildAuthHeaders(accessToken),
    });

    if (!response.ok) {
      throw new Error("Failed to fetch live feed.");
    }

    return response.json();
  } catch {
    return { status: "idle", message: "Live CCTV feed is not available." };
  }
}

export async function addCamera(accessToken, camera) {
  const response = await fetch(`${API_BASE_URL}/v1/cameras`, {
    method: "POST",
    headers: {
      ...buildAuthHeaders(accessToken),
      "Content-Type": "application/json",
    },
    body: JSON.stringify(camera),
  });

  if (!response.ok) {
    throw new Error("Failed to register camera.");
  }

  return response.json();
}

export async function uploadCameraClip(accessToken, cameraId, file) {
  const form = new FormData();
  form.append("file", file);

  // Note: do NOT set Content-Type — the browser sets the multipart boundary.
  const response = await fetch(`${API_BASE_URL}/v1/cameras/${cameraId}/clip`, {
    method: "POST",
    headers: buildAuthHeaders(accessToken),
    body: form,
  });

  if (!response.ok) {
    throw new Error("Failed to upload clip.");
  }

  return response.json();
}

export async function analyzeCameraClip(accessToken, cameraId) {
  const response = await fetch(`${API_BASE_URL}/v1/cameras/${cameraId}/analyze`, {
    method: "POST",
    headers: buildAuthHeaders(accessToken),
  });

  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new Error(detail.detail || "Failed to analyze clip.");
  }

  return response.json();
}

export async function submitFeedback(accessToken, payload) {
  const response = await fetch(`${API_BASE_URL}/v1/reports/feedback`, {
    method: "POST",
    headers: {
      ...buildAuthHeaders(accessToken),
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error("Failed to submit feedback.");
  }

  return response.json();
}