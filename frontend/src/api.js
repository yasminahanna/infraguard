import fallbackReport from "./daily_report_sample.json";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export async function getLatestReport() {
  try {
    const response = await fetch(`${API_BASE_URL}/v1/reports/latest`);

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