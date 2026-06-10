# InfraGuard — Project Report

InfraGuard is a production-oriented AI engineering system for road-safety risk analysis. It detects risky driving behaviour from CCTV camera frames, identifies emerging hotspot road segments, and generates infrastructure recommendations with an LLM-based recommender, surfaced through an admin dashboard.

---

## 1. Architecture

### 1.1 Service topology

InfraGuard is a **distributed microservice system**: one External Endpoint (EEP) and three Internal Endpoints (IEPs), each an independent FastAPI service in its own container. This exceeds the course minimum (1 EEP + 2 IEPs) and is a deliberate choice — each service owns a distinct concern, which improves testability, fault isolation, observability, and independent deployment.

```
                ┌──────────────────────────────────────────────┐
   Admin /      │                EEP GATEWAY  :8000              │
   Demo user ──▶│  (public boundary)                             │
   (browser,    │  • API-key / Supabase auth   • request valid.  │
    API client) │  • payload constraints       • orchestration   │
                │  • timeouts & fault handling • unified response │
                └───────┬──────────────┬───────────────┬─────────┘
                        │              │               │
                 (1)    ▼       (2)    ▼        (3)     ▼
            ┌───────────────┐ ┌───────────────┐ ┌──────────────────┐
            │ DETECTION IEP │ │  HOTSPOT IEP  │ │ RECOMMENDER IEP   │
            │     :8001     │ │     :8002     │ │      :8003        │
            │ YOLOv8n +     │ │ risk scoring  │ │ LLM (OpenAI) +    │
            │ CLIP zero-shot│ │ + trend vs    │ │ optional web RAG  │
            │ → events      │ │ baseline      │ │ → JSON rec.       │
            └───────────────┘ └───────────────┘ └──────────────────┘
                                                          │
                                                  emergency static
                                                  fallback if down
```

**Request flow (`POST /v1/analyze`):** the EEP authenticates and validates the request, then calls the IEPs in sequence — Detection produces structured events, those events feed Hotspot scoring, and the detection + hotspot evidence feeds the Recommender. The EEP assembles one unified response with `request_id`, all three service outputs, `fallbacks_used`, and end-to-end `latency_ms`.

### 1.2 Service responsibilities

| Service | Port | Responsibility | Implementation |
|---|---|---|---|
| **EEP Gateway** | 8000 | Public boundary: auth, validation, orchestration, timeout/failure handling, unified response. Also serves the dashboard APIs (cameras, evidence, reports, feedback, live feed). | FastAPI + httpx async orchestration |
| **Detection IEP** | 8001 | Decode camera frames → detect vehicles and classify scene-level traffic-risk events with confidence + severity. | **YOLOv8n** vehicle detection + **CLIP** zero-shot event classifier, fused into structured events; controlled demo fallback when frames aren't valid images |
| **Hotspot IEP** | 8002 | Consume detection events → compute hotspot risk score, risk level, and trend vs baseline. | Geospatial/temporal scoring logic |
| **Recommender IEP** | 8003 | Consume detection + hotspot evidence → recommend a road-safety intervention as strict validated JSON; build the daily report. | **OpenAI LLM** + optional **Tavily web RAG**; schema-validated output |

### 1.3 Key design properties

- **Fault isolation / graceful degradation** — every downstream call is wrapped with timeout, HTTP-error, and connection-error handling (HTTP 502/504). If the Recommender is unavailable, the EEP returns an explicit **emergency static fallback** (conservative `add_warning_signage`, confidence 0.25) so the deployed system stays functional and honest about degraded mode.
- **Evidence-grounded recommendations** — the recommender receives only structured summaries (not raw frames); RAG context, when used, is returned in the response for transparency.
- **Stateful dashboard layer** — camera registry, uploaded clips, daily reports, report history, and feedback are persisted on a shared volume and exposed through the EEP.

---

## 2. Software Stack

```
┌─ FRONTEND ──────────────────────────────────────────────────────────┐
│  React + Vite  │  Supabase Auth (admin login)  │  map + hotspots,    │
│                │                                │  reports, evidence  │
│  served by nginx (container)                                         │
└───────────────────────────────┬─────────────────────────────────────┘
                                 │  HTTPS/JSON  (X-API-Key / Bearer)
┌─ BACKEND (4 × FastAPI services) ────────────────────────────────────┐
│  Python 3.12 · FastAPI · Pydantic (validation) · httpx (async)       │
│  Detection: Ultralytics YOLOv8n · OpenAI CLIP · OpenCV · Pillow      │
│  Recommender: OpenAI SDK · Tavily (web RAG)                          │
└───────────────────────────────┬─────────────────────────────────────┘
                                 │
┌─ PLATFORM / OPS ────────────────────────────────────────────────────┐
│  Docker + Docker Compose  │  Kubernetes manifests (k8s/)             │
│  Prometheus (/metrics)  +  Grafana   │  GitHub Actions CI            │
│  Supabase (auth + identity)  │  Azure Blob (CCTV clips)              │
└──────────────────────────────────────────────────────────────────────┘
```

| Layer | Technology |
|---|---|
| **Language / framework** | Python 3.12, FastAPI, Pydantic, Uvicorn, httpx |
| **Computer vision** | Ultralytics YOLOv8n (vehicle detection), OpenAI CLIP (zero-shot event classification), OpenCV, Pillow |
| **LLM / RAG** | OpenAI (`gpt-4o-mini`), Tavily web search (optional) |
| **Frontend** | React, Vite, nginx, Supabase JS client |
| **Auth / identity** | Supabase Auth (dashboard login + backend bearer-token verification) |
| **Containerisation** | Docker, Docker Compose (dev + prod), Kubernetes manifests |
| **Observability** | Prometheus client (`/metrics` on every service), Grafana |
| **CI / storage** | GitHub Actions, Azure Blob Storage (CCTV clips) |

---

## 3. Deployment

### 3.1 Local (development)

Single command brings up all four services plus frontend and the observability stack:

```
docker compose up --build
```
Services: EEP `:8000`, Detection `:8001`, Hotspot `:8002`, Recommender `:8003`, Frontend `:5173`, Prometheus `:9090`, Grafana `:3000`. Configuration is via `.env` (`copy .env.example .env`); secrets are never committed.

### 3.2 Cloud (production)

Deployed to a **single Azure Linux VM** (Ubuntu 22.04, `Standard_B4ms` — 4 vCPU / 16 GB, sized for CPU-only YOLO+CLIP) running `docker-compose.prod.yml`.

```
            Internet
               │
       ┌───────┴────────┐   only ports 80 + 8000 open
       ▼                ▼
 ┌───────────┐   ┌──────────────┐
 │ Dashboard │   │ EEP Gateway  │   ──────────────┐  PUBLIC
 │   :80     │   │   :8000      │                 │
 └───────────┘   └──────┬───────┘                 │
        infraguard-net (internal docker network)  │
   ┌──────────┬─────────┼──────────┬───────────┐  │
   ▼          ▼         ▼          ▼           ▼  │  INTERNAL ONLY
Detection  Hotspot  Recommender  Prometheus  Grafana  (not internet-reachable)
 :8001      :8002     :8003        :9090       :3000
```

**Production hardening (prod compose vs dev):**
- Only the **EEP (8000)** and **dashboard (80)** are exposed publicly; all IEPs and Prometheus/Grafana stay internal on `infraguard-net` and are not internet-reachable.
- `restart: unless-stopped` on every service (survives reboots/crashes).
- `REQUIRE_SUPABASE_AUTH` defaults to `true` (admin-gated dashboard in the cloud).
- Frontend built against the public EEP URL; secrets injected via `.env` / env vars, never committed.

**Rollback strategy:** keep the previous working image tag, tag the last stable commit, and `git checkout <last-good>` + rebuild (or `compose down` and re-up the prior commit) if a deploy fails health checks.

**Cost control:** `az vm deallocate` between demos stops compute billing; billing alerts set; `az group delete` for full teardown after grading. A full scaling cost model (pilot → district → full city) is documented — detection compute is the dominant driver, and periodic sampling keeps even a 2,500-camera city deployment at ~$11.5k/mo vs ~$193k/mo for blanket near-real-time.

**Kubernetes:** manifests (namespace, deployments, services, ingress, configmap, secrets template) are provided in `k8s/` for a future managed-cluster migration.

---

## 4. Testing & QA

### 4.1 Test pyramid

| Level | Scope | Status |
|---|---|---|
| **Unit / API** | Per-service: health, valid requests, schema-constraint rejection, business logic | Detection 4 · Hotspot 5 · Recommender 11 · EEP 3 |
| **Integration** | EEP orchestration across all three IEPs; API-key rejection; invalid-payload rejection | 3 passing |
| **End-to-end (deployed)** | Calls the hosted public EEP `/v1/analyze` and asserts detection + hotspot + recommendation present | Gated on `DEPLOYED_EEP_URL` / `DEPLOYED_API_KEY`; runs against the live VM |
| **Golden eval data check** | Validates the golden recommender cases (structure, allowed interventions/priorities) | Runs in CI |

~26 local tests + 1 deployed E2E across 9 test files.

### 4.2 Continuous Integration (GitHub Actions)

On every push/PR the CI runs, as separate jobs: Detection / Hotspot / Recommender / EEP test suites, a **`docker compose build`** check (all images build), and the **golden eval data validation**. This means no change merges without all services passing tests and all containers building.

### 4.3 LLM-specific QA

LLM output is non-deterministic, so tests assert **structure, not exact text**: valid JSON, schema compliance, allowed intervention values, required evidence fields, confidence within range, and no invented fields. Failure-mode tests cover missing OpenAI key, recommender unavailable, invalid API key, too many frames, and invalid confidence.

---

## 5. Validation of the Project

This section is the core evidence that InfraGuard works, is correct, and behaves safely — not just that it runs.

### 5.1 Functional validation — the system does what it claims

- **Real CV inference, not a stub.** The Detection IEP decodes real base64 frames, runs **YOLOv8n** for vehicles and **CLIP zero-shot** for scene events, and fuses them into structured, severity-and-confidence-labelled events. `models_used` and `decoded_real_frames` in the response prove which path executed; the demo fallback fires only when frames are not valid images.
- **End-to-end orchestration validated against the live deployment.** The deployed E2E test calls the hosted public EEP and asserts a `completed` response containing detection, hotspot, and recommendation outputs — confirming the full distributed path works in the cloud, not only locally.
- **Network isolation validated.** Deployment verification confirms the IEP ports (8001–8003) are *not* publicly reachable while the EEP and dashboard are — validating the security boundary.

### 5.2 Output validation — recommendations are correct and safe

The Recommender enforces a **strict contract** on LLM output:
- JSON is parsed and **schema-validated with Pydantic**; malformed JSON or schema violations are rejected (HTTP 502, metric `schema_validation_failed`) rather than passed downstream.
- `primary_intervention` must be one of a **fixed allowed set**; `priority` ∈ {low, medium, high}; `confidence` is range-checked; evidence fields are required.

### 5.3 Golden-case regression validation

A curated set of **golden recommender cases** (`evals/golden_recommender_cases.json`) encodes expected behaviour for representative scenarios (high-speeding hotspot, medium-risk lane violation, low-risk monitoring). Each case asserts:
- **acceptable interventions** (output must fall within a sensible set),
- **minimum priority** (e.g. a high-risk hotspot may not be down-graded),
- **`must_use_evidence`** (the recommendation must cite the real signals — e.g. `hotspot_score`, `risk_level`),
- **`must_not_claim`** (safety guardrails — must not claim "legally required" or "guaranteed crash reduction").

These cases are structurally validated in CI today and form the regression baseline for prompt/model changes.

### 5.4 Robustness / failure-mode validation

Validated degradation behaviour: recommender-down → explicit emergency fallback (system stays up, clearly flagged); downstream timeout/error → controlled 502/504 with the failing service named; invalid API key → 401; oversized payload (>8 frames) → 422 at the validation boundary.

### 5.5 Honest limitations (validation integrity)

The project is explicit about what is *not* yet validated, which is itself part of sound validation practice:
- **Dataset-backed accuracy metrics** for detection/hotspot are planned, not yet measured — the CV models are integrated and produce real outputs, but precision/recall against a labelled traffic dataset is future work.
- **Fine-tuning** is deferred until enough reviewed examples exist; the system uses RAG + golden evaluation instead and does **not** claim learned intervention labels.
- **MLflow lifecycle tracking** (experiment/version/promotion logging) is planned but not yet wired in.
- The daily-report backend is partially sample-data backed while the live generator is finalised.

### 5.6 Observability as continuous validation

Every service exposes Prometheus `/metrics` — request counts, latency histograms (p50/p95), per-event-type counters, downstream IEP failure counts, and LLM failure types — scraped by Prometheus and visualised in Grafana. This gives ongoing runtime validation of latency, error rates, and LLM JSON-validity in production, beyond point-in-time tests.

---

## 6. Summary

InfraGuard is a genuinely distributed, containerised AI system — four independent FastAPI services with real computer-vision (YOLOv8n + CLIP) and LLM+RAG components, an authenticated React dashboard, full CI, Prometheus/Grafana observability, and a hardened single-VM Azure deployment with only the public surface exposed. Validation spans functional (live E2E orchestration), output correctness (strict schema + allowed-value enforcement), regression (golden cases with evidence-grounding and safety guardrails), and robustness (validated fallback/timeout/auth behaviour), backed by continuous runtime metrics. Remaining work — dataset-backed accuracy metrics, MLflow tracking, and the live report generator — is documented honestly rather than overclaimed.
