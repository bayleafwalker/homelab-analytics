# OIDC enablement against Authentik

This runbook switches a deployed homelab-analytics from `local_single_user` to `oidc`, with Authentik as the identity provider. The application side is already built and tested against a local fake IdP (`tests/test_oidc_authentik_flow.py`). This page covers what only the operator can do: create the Authentik objects, place the secrets, roll the change out through GitOps, and verify it.

Configuration reference: `docs/runbooks/configuration.md` § Supported defaults: oidc.

## What changes for users

- `/login` shows a "Sign In with OIDC" button instead of the local password form.
- Roles come from Authentik groups. **No group means no access**: a user in none of the role groups is refused with `/login?error=oidc-unmapped`.
- Service tokens (MCP agents, the HA bridge) keep working unchanged.
- Proposal approvals and decision-ledger entries record the Authentik username with `auth_provider=oidc`.
- The local `admin` login and break-glass stop applying while the mode is `oidc`. Rolling back (below) restores them.

## 1. Authentik: groups

Create three groups (**Directory → Groups → Create**), and add users to them:

| Group | App role | Can |
|---|---|---|
| `hla-readers` | `reader` | read reports, proposals and decisions |
| `hla-operators` | `operator` | the above, plus approve or dismiss agent proposals, record decisions, retry runs |
| `hla-admins` | `admin` | everything, including `/control` configuration, policies and service tokens |

A user in several groups gets the highest role. Put at least one person in `hla-admins` before cutting over.

## 2. Authentik: OAuth2/OpenID provider

Go to **Applications → Providers → Create → OAuth2/OpenID Provider** and set:

| Field | Value |
|---|---|
| Name | `homelab-analytics` |
| Authorization flow | `default-provider-authorization-implicit-consent`, or the explicit-consent flow if you want a consent screen |
| Client type | **Confidential** |
| Client ID / Client Secret | Keep the generated values. You need both in step 4 |
| Redirect URIs | `https://analytics.<your-domain>/auth/callback`, with matching mode **Strict** |
| **Signing Key** | **Select a certificate**, for example `authentik Self-signed Certificate`. Required: without a signing key Authentik signs ID tokens with HS256 using the client secret, and homelab-analytics refuses HMAC-signed tokens |
| Scopes (advanced) | `openid`, `email`, `profile`. The default `profile` mapping emits `preferred_username` and `groups` |
| Subject mode | Default (hashed user ID) is fine. It becomes `user_id = oidc:<sub>` in the auth audit log |
| Include claims in id_token | **On**, so `groups` and `preferred_username` are in the ID token |

PKCE needs no setting. Authentik accepts S256 challenges from any client.

## 3. Authentik: application

Go to **Applications → Applications → Create** and set:

- Name: `Homelab Analytics`.
- Slug: `homelab-analytics`. The slug fixes the issuer URL.
- Provider: `homelab-analytics`.
- Launch URL: `https://analytics.<your-domain>/`.
- Optional: under **Policy / Group / User Bindings**, bind the three `hla-*` groups so that nobody else can even start the flow.

The issuer is `https://<authentik-host>/application/o/homelab-analytics/` and it **ends with a slash**. Use it verbatim.

## 4. Secrets (SOPS, in the cluster repo)

All cluster changes go through a PR against `appservice` (`clusters/main/kubernetes/apps/homelab-analytics/`), and Flux reconciles them. Do not `kubectl apply` by hand.

Add these keys to the existing SOPS-encrypted `runtime-auth.secret.yaml`, which already holds `HOMELAB_ANALYTICS_SESSION_SECRET`:

```yaml
stringData:
  HOMELAB_ANALYTICS_OIDC_CLIENT_ID: "<client id from step 2>"
  # Either the literal secret ...
  HOMELAB_ANALYTICS_OIDC_CLIENT_SECRET: "<client secret from step 2>"
  # ... or a SecretResolver reference (set REF in the env and drop the literal):
  # HOMELAB_ANALYTICS_SECRET__AUTHENTIK_HLA__CLIENT_SECRET: "<client secret>"
```

Edit it with `sops clusters/main/kubernetes/apps/homelab-analytics/runtime-auth.secret.yaml`. Keep the existing session secret: rotating it signs everyone out, which is harmless but unnecessary.

## 5. Environment (api container, and web where noted)

| Variable | Value | Container |
|---|---|---|
| `HOMELAB_ANALYTICS_IDENTITY_MODE` | `oidc` | api **and** web |
| `HOMELAB_ANALYTICS_OIDC_ISSUER_URL` | `https://<authentik-host>/application/o/homelab-analytics/` | api |
| `HOMELAB_ANALYTICS_OIDC_REDIRECT_URI` | `https://analytics.<your-domain>/auth/callback` | api |
| `HOMELAB_ANALYTICS_OIDC_READER_GROUPS` | `hla-readers` | api |
| `HOMELAB_ANALYTICS_OIDC_OPERATOR_GROUPS` | `hla-operators` | api |
| `HOMELAB_ANALYTICS_OIDC_ADMIN_GROUPS` | `hla-admins` | api |
| `HOMELAB_ANALYTICS_OIDC_CLIENT_SECRET_REF` | `authentik-hla/client_secret` (only if you used the reference form in step 4) | api |
| `HOMELAB_ANALYTICS_BREAK_GLASS_ENABLED` | remove, or leave it; it is ignored outside `local_single_user` | api |
| `HOMELAB_ANALYTICS_ENABLE_BOOTSTRAP_LOCAL_ADMIN` | `false` | api |

Leave the defaults for `HOMELAB_ANALYTICS_OIDC_SCOPES` (`openid,profile,email`), `_USERNAME_CLAIM` (`preferred_username`), `_GROUPS_CLAIM` (`groups`) and `_JWKS_CACHE_SECONDS` (`3600`). The api pod must reach the Authentik host over HTTPS: discovery, JWKS and the token endpoint are server-side calls. The browser only visits the authorization endpoint.

## 6. Verify

Before merging, from any shell that can reach Authentik:

```bash
curl -fsS https://<authentik-host>/application/o/homelab-analytics/.well-known/openid-configuration \
  | jq '{issuer, id_token_signing_alg_values_supported, code_challenge_methods_supported}'
```

Expected: the `issuer` ends in `/application/o/homelab-analytics/`, the algorithm list contains `RS256` (or `ES256`) and is **not** only `HS256`, and `code_challenge_methods_supported` contains `S256`.

After Flux reconciles:

1. The api container in namespace `analytics` (context `appservice`) is ready and its log has no `api startup configuration invalid` line. The api refuses to start if a required OIDC setting is missing, or if both the secret and the secret reference are set.
2. Open `https://analytics.<your-domain>/login`. It shows "Sign In with OIDC", which goes to Authentik and comes back to the page you started from.
3. Open `https://analytics.<your-domain>/auth/me` (API JSON) in the same browser. Expect `"auth_mode": "oidc"`, `"auth_provider": "oidc"`, your Authentik username, and the role from your group.
4. As an `hla-operators` member, open `/control/agents`, approve or dismiss a test proposal, and check its history line. It should read `… · <username> (oidc)`.
5. Sign in as a user with no `hla-*` group. Expect `/login?error=oidc-unmapped`.
6. Check that an existing MCP service token still works: `curl -H "Authorization: Bearer <token>" https://analytics.<your-domain>/api/agent/catalog` returns `200`.

## Rollback

Set `HOMELAB_ANALYTICS_IDENTITY_MODE` back to `local_single_user` on api and web, with `HOMELAB_ANALYTICS_BREAK_GLASS_ENABLED=true`, in the same `appservice` PR flow. The OIDC variables can stay; they are ignored outside `oidc`. Sessions issued under OIDC stop validating after the switch, and users sign in locally again.

## What to send back

- The issuer URL and the discovery `jq` output from step 6.
- The `/auth/me` JSON for one operator and one admin. Redact nothing: it holds no secrets.
- Whether steps 4 to 6 behaved as expected, and the exact `/login?error=…` value if anything failed.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `/login?error=oidc-failed` straight after Authentik | Redirect URI mismatch, wrong client secret, or no signing key, so tokens are HS256. Check the api log for `login_failed` auth-audit detail |
| `/auth/login` returns `502` | The api cannot reach discovery, the issuer is mistyped, or the IdP does not offer S256 |
| `/login?error=oidc-unmapped` for a real user | The user is in no `hla-*` group, or "Include claims in id_token" is off |
| Works, then fails after an Authentik certificate rotation | Wait about 10 s and retry: an unknown `kid` forces a JWKS refetch, rate-limited to once every 10 s |
