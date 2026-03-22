# ADR: External Identity, Internal Authorization, and Narrow Break-Glass

**Status:** Accepted
**Owner:** Juha
**Decision type:** Security and platform-boundary architecture
**Applies to:** API auth runtime, web auth flows, worker token consumers, control-plane auth policy

---

## 1. Executive summary

The platform boundary is:

- authentication identity proof belongs to an upstream identity provider by default
- authorization policy belongs to homelab-analytics because permission semantics are app-specific
- machine access uses app-managed permission scopes now, with a path to upstream machine JWTs later
- local username/password is a narrow fallback mode, not a parallel multi-user identity system

This keeps identity lifecycle complexity outside the app while preserving strict control over app actions.

---

## 2. Context

The current implementation already supports:

- local session login and bootstrap admin flow
- OIDC login and bearer-token validation
- service tokens with scoped route checks
- group-to-role mapping

That is enough surface area to accidentally grow a second identity product inside the platform unless the boundary is explicit.

---

## 3. Decision

### 3.1 Authentication boundary

Interactive human authentication defaults to OIDC through an upstream provider.

The app should treat upstream claims as inputs to principal construction, not as a reason to own user lifecycle features such as MFA, password reset, or account recovery.

### 3.2 Authorization boundary

Authorization remains app-local.

The app owns:

- principal normalization
- role and permission evaluation
- app-specific resource and action semantics
- auth policy audit events

The policy model should evolve from role-only checks toward role bundles over explicit permissions.

### 3.3 Machine auth boundary

Service tokens remain a first-class path for automation and bootstrap environments.

Service-token scopes should map to the same internal permission registry used for human principals. Upstream-issued machine JWTs are an optional future alternative, not a blocker for current operation.

### 3.4 Local auth posture

Local auth is demoted to `local_single_user` semantics and break-glass fallback.

It is intentionally constrained:

- no general multi-user lifecycle
- no self-service account management expectations
- off by default in shared deployments
- treated as emergency/bootstrap access, not the primary ingress path

### 3.5 Break-glass posture

Break-glass must be explicit, temporary, and auditable:

- disabled by default
- internal-only exposure
- TTL-bounded credentials/tokens
- high-visibility audit and health signaling while active

---

## 4. Provider posture

The platform supports generic OIDC providers.

Operational default reference:

- Authentik

Supported examples:

- Authentik
- Authelia
- Keycloak

The app should avoid provider-specific assumptions beyond standards-compliant OIDC behavior.

---

## 5. Configuration evolution

Current runtime supports:

- `HOMELAB_ANALYTICS_IDENTITY_MODE=disabled|local|local_single_user|oidc|proxy`
- `HOMELAB_ANALYTICS_AUTH_MODE` as a compatibility fallback when identity mode is not set

Target config shape:

```yaml
auth:
  identity_mode: oidc | proxy | local_single_user | disabled
  authorization_mode: local_policy
  break_glass:
    enabled: false
```

Compatibility mapping during migration:

- `local` -> `local_single_user`
- `oidc` -> `oidc`
- `disabled` -> `disabled`

---

## 6. Implementation sequence

1. Document and enforce the auth boundary in requirements, architecture, runbooks, and roadmap notes.
2. Introduce an internal permission registry behind existing `reader/operator/admin` checks.
3. Map OIDC claims and service-token scopes into the shared permission vocabulary.
4. Add a trusted proxy identity mode without weakening authorization checks.
5. Narrow local auth paths to single-user/break-glass operational semantics.

Implementation status (2026-03-22): sequence complete. Remaining future-facing work is optional machine-JWT federation patterns and eventual retirement timing for compatibility env aliases.

---

## 7. Non-goals

This decision does not introduce:

- platform-managed user lifecycle features
- full externalized policy decision services as a default dependency
- provider-specific custom auth logic in the core runtime

---

## 8. Consequences

Positive:

- smaller long-term security maintenance surface
- clearer ownership boundaries
- consistent auth semantics across humans and automation

Tradeoffs:

- local auth ergonomics become intentionally narrower in production use
- `HOMELAB_ANALYTICS_AUTH_MODE` remains as a compatibility input during migration; deployments should use `HOMELAB_ANALYTICS_IDENTITY_MODE`
