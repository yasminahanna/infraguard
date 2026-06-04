# Admin Dashboard Plan

## Purpose

The final InfraGuard product should include a hosted admin-only website.

The dashboard will allow authorized users to view road safety insights produced by the AI backend.

## Users

Primary users:

- city safety administrators,
- transportation engineers,
- project evaluators,
- demo admins.

The dashboard is not intended for public anonymous access.

## Main Features

### Admin Login

Only authorized admins should access the dashboard.

Possible options:

- simple demo login,
- Auth0,
- Firebase Auth,
- Supabase Auth,
- cloud provider identity service.

### Map View

The dashboard should include an interactive map.

Map features:

- hotspot markers,
- road segment risk colors,
- camera locations,
- selected segment details,
- trend indicators.

Possible map tools:

- Leaflet,
- Mapbox,
- Google Maps.

### Hotspot Panel

For a selected road segment, show:

- hotspot score,
- risk level,
- trend,
- number of detected events,
- event types,
- confidence values,
- timestamp.

### Recommendation Panel

For a selected hotspot, show:

- primary intervention,
- priority,
- supporting actions,
- explanation,
- evidence used,
- retrieved RAG context if available,
- fallback status.

### Admin Metrics

Show system health:

- API request count,
- detection latency,
- hotspot latency,
- recommender latency,
- fallback count,
- LLM/RAG status.

## Backend Integration

The dashboard will call the EEP Gateway.

Example flow:

Admin uploads or selects a camera frame  
→ frontend calls `/v1/analyze`  
→ EEP orchestrates IEPs  
→ dashboard displays detection, hotspot, and recommendation results.

## Deployment Plan

The dashboard can be hosted separately from the AI services.

Possible hosting options:

- Vercel for Next.js,
- Netlify for React,
- Azure Static Web Apps,
- cloud container if backend and frontend are combined.

## Security

Required:

- admin-only access,
- no public access to internal IEPs,
- API key or token between frontend/backend,
- secrets stored in cloud environment variables,
- no OpenAI or Tavily keys exposed in frontend code.

## Demo Scope

Minimum demo dashboard:

- login screen,
- map with sample hotspot markers,
- selected hotspot details,
- recommendation panel,
- button to run analysis on a sample request.

Full production dashboard:

- persistent database,
- user management,
- historical hotspot trends,
- role-based access,
- audit logs,
- real-time monitoring.