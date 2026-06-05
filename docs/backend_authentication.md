# Backend Authentication

## Current Security Model

InfraGuard uses two layers of access control:

1. Supabase Auth for admin dashboard login.
2. EEP Gateway authentication for backend access.

## Dashboard Authentication

The admin dashboard uses Supabase Auth.

Admins must sign in with an email/password account created in Supabase Authentication.

After login, the frontend receives a Supabase access token.

## Backend Report Authentication

The dashboard sends the Supabase access token to the EEP Gateway using:

    Authorization: Bearer <supabase_access_token>

The EEP Gateway can verify this token when:

    REQUIRE_SUPABASE_AUTH=true

When enabled, unauthenticated requests to:

    GET /v1/reports/latest

are rejected.

## Admin Email Allowlist

The backend can restrict access to approved admin emails using:

    SUPABASE_ADMIN_EMAILS

Example:

    SUPABASE_ADMIN_EMAILS=admin@example.com,second-admin@example.com

If this list is set, only users with matching Supabase account emails are allowed.

## Local Development Mode

For local development, Supabase backend verification can be disabled:

    REQUIRE_SUPABASE_AUTH=false

In this mode, the dashboard can still use Supabase login, but the backend report endpoint does not require token verification.

## Strict Hosted Mode

For hosted deployment, use:

    REQUIRE_SUPABASE_AUTH=true

Required variables:

    SUPABASE_URL
    SUPABASE_ANON_KEY
    SUPABASE_ADMIN_EMAILS

## Existing API Key Protection

The on-demand analysis endpoint still uses:

    X-API-Key

for:

    POST /v1/analyze

This protects direct analysis calls from unauthenticated use.

## Secrets Policy

Never commit:

- `.env`
- `frontend/.env`
- OpenAI API keys
- Tavily API keys
- Supabase service role keys

The Supabase anon key is allowed in frontend configuration, but the service role key must never be used in frontend code.