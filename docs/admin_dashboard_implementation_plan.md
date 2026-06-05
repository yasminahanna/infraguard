# Admin Dashboard Implementation Plan

## Goal

Build a hosted admin-only dashboard for InfraGuard.

The dashboard should let admins view:

- hotspot locations,
- risk levels,
- detection events,
- recommendations,
- retrieved RAG context,
- system status.

## Recommended Frontend

Use:

- React or Next.js
- Leaflet for the map
- simple username/password demo login at first

Why:

- easy to host,
- easy to build quickly,
- Leaflet is free and simple,
- works well for a demo map.

## Minimum Demo Features

The first dashboard version should include:

1. Login screen
2. Main dashboard page
3. Map with hotspot marker
4. Selected hotspot details panel
5. Recommendation panel
6. Button to run sample analysis
7. Basic system status section

## Pages

### `/login`

Purpose:

- admin login page.

For demo:

- use one hardcoded admin username/password stored in environment variables.

Later:

- replace with Auth0, Firebase Auth, Supabase Auth, or cloud identity.

### `/dashboard`

Purpose:

- main admin dashboard.

Sections:

- map,
- hotspot details,
- recommendation details,
- system health.

## Backend Connection

The dashboard calls the EEP Gateway.

Main request:

    POST /v1/analyze

Required header:

    X-API-Key

The API key must not be exposed directly in frontend code in a production system.

For the final demo, use a small dashboard backend/proxy or protected environment variable depending on hosting setup.

## Map

Use Leaflet.

Marker data can come from:

- sample response,
- `/v1/analyze` response,
- later database records.

Each marker should show:

- road segment ID,
- risk level,
- hotspot score,
- recommendation priority.

## Data Storage

Minimum demo:

- no database required,
- dashboard can display the latest analysis response.

Better version:

- store results in PostgreSQL or SQLite.

Future production version:

- PostgreSQL with PostGIS for geospatial hotspot storage.

## Security

Required:

- admin-only access,
- no OpenAI key in frontend,
- no Tavily key in frontend,
- no internal IEP URLs exposed publicly,
- EEP API key protected.

## Hosting

Recommended:

- Vercel for frontend,
- Azure Container Apps for backend.

Backup:

- Azure Static Web Apps for frontend,
- Google Cloud Run for backend.

## Implementation Order

1. Create frontend folder.
2. Add simple React/Next.js app.
3. Add login page.
4. Add dashboard page.
5. Add Leaflet map.
6. Add sample hotspot marker.
7. Connect to EEP `/v1/analyze`.
8. Display detection, hotspot, and recommendation response.
9. Host frontend.
10. Test full hosted flow.