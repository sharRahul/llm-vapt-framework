# Future Plan: OIDC/JWT Authentication

## 1. Decision and timing

OIDC/JWT support is a future enterprise-hardening item, not a current local-use requirement. The current VulnoraIQ posture is single-user, self-hosted laptop/workstation or controlled internal-server use with token auth, trusted reverse-proxy identity, CSRF, rate limits, audit logs, and production startup validation. Implement OIDC/JWT when VulnoraIQ is expected to support multiple users, enterprise SSO, central MFA, central offboarding, or role assignment from an identity provider.

This plan must not make OIDC mandatory for the Docker-first local lab or standalone launcher. Local laptop use should remain simple and loopback-only by default.

## 2. Goals and non-goals

Goals:

- Add optional direct OIDC/JWT authentication for enterprise deployments.
- Validate bearer tokens locally using issuer, audience, expiry, not-before, allowed algorithms, and JWKS key material.
- Map identity-provider claims to existing VulnoraIQ roles: `viewer`, `analyst`, and `admin`.
- Preserve current token and trusted-proxy modes.
- Emit audit events using the resolved enterprise identity.
- Keep production startup validation fail-closed when OIDC/JWT is incomplete or unsafe.

Non-goals:

- Do not add a full browser login flow in the first implementation.
- Do not store identity-provider passwords or refresh tokens.
- Do not replace reverse-proxy SSO support.
- Do not require OIDC/JWT for local Docker Compose or launcher use.

## 3. Configuration design

Add a third auth mode:

```bash
VULNORAIQ_AUTH_MODE=token|trusted_proxy|oidc_jwt
```

Recommended OIDC/JWT environment variables:

```bash
VULNORAIQ_OIDC_ISSUER=https://issuer.example.com/
VULNORAIQ_OIDC_AUDIENCE=vulnoraiq-api
VULNORAIQ_OIDC_JWKS_URL=https://issuer.example.com/.well-known/jwks.json
VULNORAIQ_OIDC_ALLOWED_ALGORITHMS=RS256
VULNORAIQ_OIDC_USERNAME_CLAIM=preferred_username
VULNORAIQ_OIDC_ROLES_CLAIM=roles
VULNORAIQ_OIDC_GROUPS_CLAIM=groups
VULNORAIQ_OIDC_ROLE_MAPPING=VulnoraIQ-Admins:admin,VulnoraIQ-Analysts:analyst,VulnoraIQ-Viewers:viewer
VULNORAIQ_OIDC_DEFAULT_ROLE=viewer
VULNORAIQ_OIDC_REQUIRE_ROLE=true
```

Default to fail-closed in production when `oidc_jwt` mode is selected and issuer, audience, JWKS URL, or allowed algorithms are missing.

## 4. Authentication flow

Implementation target: `webui/auth.py` and `webui/hosted_server.py`.

Flow:

1. Read `Authorization: Bearer <jwt>`.
2. Reject missing, malformed, unsigned, or unsupported-algorithm tokens.
3. Resolve the token `kid` against a cached JWKS document.
4. Validate signature, issuer, audience, expiry, not-before, and optional required claims.
5. Build `AuthPrincipal(username, role, permissions, authenticated=True)`.
6. Return `401` for invalid authentication and `403` for valid users without required permissions.

JWKS caching should have a bounded TTL, safe retry handling, and no token value logging.

## 5. Role mapping and audit

Keep the existing VulnoraIQ permission model. OIDC/JWT should only translate external claims into existing roles.

Role resolution order:

1. explicit role claim match;
2. group claim match;
3. configured default role if allowed;
4. reject when `VULNORAIQ_OIDC_REQUIRE_ROLE=true` and no mapping matches.

Audit events should record:

- resolved username;
- resolved role;
- authentication mode `oidc_jwt`;
- request ID;
- client IP after trusted proxy resolution;
- endpoint path and status.

Audit logs must never include raw bearer tokens, JWKS content, secrets, or full identity-provider responses.

## 6. Production validation

Update `webui/production_checks.py` so production mode accepts OIDC/JWT as a valid auth path when all required settings are safe. In `oidc_jwt` mode, do not require `VULNORAIQ_ADMIN_TOKEN`; instead require issuer, audience, JWKS URL, allowed algorithms, and safe role mapping.

Production checks should fail for:

- `alg=none` or missing algorithm allowlist;
- missing issuer or audience;
- missing JWKS URL;
- insecure HTTP JWKS URL unless explicitly allowed for local test fixtures;
- wildcard audience;
- empty role mapping when role is required;
- debug logging that could expose token details.

## 7. Test and documentation plan

Tests:

- valid token authenticates with viewer, analyst, and admin mappings;
- expired token is rejected;
- wrong issuer is rejected;
- wrong audience is rejected;
- unsupported algorithm is rejected;
- unknown `kid` is rejected;
- missing role is rejected when required;
- missing role falls back to default when allowed;
- `/api/session` reports the resolved enterprise identity;
- production validation passes for complete OIDC/JWT config;
- production validation fails for incomplete or unsafe OIDC/JWT config.

Documentation:

- update `README.md`, `SECURITY.md`, `docs/getting-started/installation.md`, and `docs/security/security-model.md`;
- add provider examples for Microsoft Entra ID, Okta/Auth0-style providers, and Keycloak;
- document reverse-proxy SSO versus direct bearer-token validation decision criteria.

## 8. Rollout checklist

1. Implement `oidc_jwt` mode behind environment variables.
2. Add offline unit tests with generated test keys and JWKS fixtures.
3. Add hosted WebUI API tests for `/api/session` and protected endpoints.
4. Update production validation and CI coverage.
5. Document provider configuration examples.
6. Keep token and trusted-proxy modes fully backward compatible.
7. Mark enterprise identity complete only after CI is green and docs are updated.
