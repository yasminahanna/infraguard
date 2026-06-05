# Admin Authentication

## Current Implementation

InfraGuard uses Supabase Auth for the admin dashboard login.

Admins sign in using an email and password account created in Supabase Authentication.

The frontend stores the Supabase session through the Supabase client library and only loads the dashboard after a valid session is available.

## Environment Variables

Frontend environment variables:

    VITE_SUPABASE_URL
    VITE_SUPABASE_ANON_KEY
    VITE_API_BASE_URL

The Supabase anon key is allowed in frontend code.

The Supabase service role key must never be exposed in frontend code.

## Current Backend Protection

The EEP Gateway is protected by an API key using the `X-API-Key` header.

This protects backend API calls from unauthenticated public use.

## Production Security Goal

For production, the EEP Gateway should also verify the Supabase JWT from the logged-in admin.

The intended request flow is:

Admin logs in with Supabase  
→ frontend receives Supabase access token  
→ frontend sends token to EEP Gateway  
→ EEP verifies token  
→ EEP returns daily report or analysis result

## Future Backend Verification

The EEP Gateway should eventually check:

- valid Supabase JWT,
- token expiration,
- issuer,
- project audience,
- admin role or approved admin email.

## Security Rules

Required:

- never commit `.env`,
- never expose Supabase service role key,
- never expose OpenAI key in frontend,
- never expose Tavily key in frontend,
- protect EEP with API key or JWT verification,
- keep internal IEP services private when deployed.

## Demo Scope

For the current demo:

- Supabase Auth protects dashboard access.
- EEP API key protects backend access.
- Future work includes full backend JWT verification.