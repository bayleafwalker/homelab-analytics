# Agentic UX and vuoro alignment (2026-10)

**Status:** first pass implemented on `feat/agentic-ux-vuoro-alignment`. The vuoro-side items in section 5 are still proposals.
**Scope:** the agent-facing surfaces of homelab-analytics (HLA): the MCP tools, the semantic index, the action-proposal queue, the operator's view of all three, the AssistantRuntime boundary (Kotona brief Stage B2), and how HLA lines up with vuoro / vuoro-cloud.
**Rules that still apply:** app-facing reads go through publications and the reporting layer. Agents never get landing shortcuts. Every action stays approval-gated. No device actuation or credentials are added. No LLM provider calls are wired to production paths.

---

## 1. What existed before this pass (verified 2026-10-18)

| Surface | Where | Behaviour |
|---|---|---|
| MCP server | `apps/agent/mcp_server.py` | Five tools: `list_publications`, `get_publication_summary`, `propose_scenario`, `propose_policy`, `propose_action`. Raw HTTP payloads came back as tool text, `isError` was set on status ≥ 400, and arguments were not validated before the call. |
| Semantic index | `packages/platform/agent_semantic_index.py`, `GET /api/agent/semantic-index[/{key}]` | Per publication: summary, column glossary, and a bounded sample. **No freshness or confidence**, and no paging. |
| Proposal queue | `packages/platform/action_proposals.py`, `/api/actions/proposals*` (shared with `/api/ha/actions/proposals*`) | In-memory registry with three states: `pending` / `approved` / `dismissed`. |
| Operator view | `/homelab` only (HA approval cards) | Generic agent proposals had **no operator surface** beyond the HA cards, and there was no evidence, diff, or audit view. |
| Assistant | `GET /api/assistant/answer` | Deterministic answer per domain, with `answer_confidence`. |

## 2. Friction and defects found

These are ordered by severity. Every item marked **fixed** is fixed in this branch and has a test.

1. **An agent could approve its own proposal (fixed).** `POST /api/actions/proposals` and `.../approve` used the same `admin:write` scope, so any token able to draft could also approve. Machine principals (`service_token`, `machine_jwt`) now get a `403` when they try to resolve a proposal, on both route families (`resolver_identity`, `apps/api/routes/action_proposal_routes.py`).
2. **Resolved proposals could be flipped (fixed).** `approve()` or `dismiss()` on an already-resolved proposal silently overwrote the operator's decision, and the HA dispatcher's condition-cleared path could dismiss an approved proposal. Only `pending` resolves now. A second attempt returns `409`, and the dispatcher treats it as a no-op.
3. **`propose_policy` created live policies (fixed).** `PolicyDefinitionCreate.enabled` defaults to `True`, so a "draft" was evaluated immediately and recorded `source_kind="operator"` with a creator the caller supplied. Machine-principal creates are now stored disabled with `source_kind="agent"` and the token name as creator, and machine principals cannot enable a policy.
4. **`propose_policy` cannot be reached with a service token.** `/control/policies` needs `control.policy.write`, which no service-token scope grants. The tool works only with auth disabled or with a machine JWT bound to that permission. The catalog now reports this honestly (`token_reachable: false` plus an `access_note`). Section 6 asks the operator to decide.
5. **Confidence key namespace split (worked around).** The refresh path records confidence snapshots under the relation name (`mart_monthly_cashflow`). Contracts, the semantic index, and agents use the contract key (`monthly_cashflow`). A naive lookup would read every publication as `trust_unknown`. `build_publication_confidence_lookup` (`apps/api/routes/agent_routes.py`) bridges the two. The assistant routes' hardcoded `mart_*` key lists happen to match the snapshot namespace. The real fix is to pick one key, and that needs a coordination decision with the confidence owner. **Resolved (wave 2, `refactor/core-split-and-dedupe`):** the relation name is the canonical snapshot key, matching lineage, refresh handlers, control-plane publication definitions, policies, and the morning brief. `PublicationKeyResolver` (`packages/platform/publication_keys.py`) is the single mapping; writes canonicalize through it, contract and agent reads resolve through `get_latest_publication_confidence(..., key_resolver=...)` and still read legacy contract-keyed snapshots, and the agent-route bridge is removed.
6. **No answer-honesty signal for agents (fixed).** See section 3.
7. **No resolver audit (fixed).** Proposals now record `resolved_by`, `resolution_reason`, and an append-only `history` (`drafted` / `refreshed` / `approved` / `dismissed`).
8. **The proposal queue lives in memory (open).** It is lost on API restart, and the UI says so. Persisting it needs a migration, and the decision-ledger work currently owns that space (section 7).

## 3. What agents see now (MCP and API)

The single tool catalog is `packages/application/use_cases/agent_tool_catalog.py`. The MCP `tools/list` and the operator's `GET /api/agent/catalog` both come from it, so they cannot drift apart.

| Tool | Effect | Reads | Scope | vuoro operation |
|---|---|---|---|---|
| `list_publications` | read | semantic index (paged: `limit` / `cursor`, `total`, `next_cursor`) | `reports:read` | `hla.publication.list` |
| `get_publication_summary` | read | the named publication, plus `answer_guidance` | `reports:read` | `hla.publication.describe` |
| `get_publication_lineage` (new) | read | lineage metadata, no rows | `reports:read` | `hla.publication.trace` |
| `get_proposal` (new) | read | proposal status, resolver, history | `reports:read` | `hla.proposal.get` |
| `propose_scenario` | draft | scenario engine | `reports:read` | `hla.scenario.propose` |
| `propose_policy` | draft (disabled) | cited publication | n/a for tokens (see 2.4) | `hla.policy.propose` |
| `propose_action` | draft (queue) | cited publications; optional `idempotency_key` | `admin:write` | `hla.proposal.create` |

**Trust guidance.** Every semantic-index entry carries a `trust` block derived from the latest confidence snapshot (`packages/application/use_cases/agent_trust.py`). `guidance` takes one of four values:

- `state_as_current`
- `state_with_caveat`: degraded, due soon, or a validation or completeness signal is not `known`
- `do_not_state_as_current`: stale, unreliable, or unavailable
- `trust_unknown`: no snapshot exists. This is **never** read as current.

The block also carries `validation_state` and `completeness_state` (from PR #28). On `initialize`, the MCP server returns `instructions` that require agents to follow the guidance, to avoid computing totals from truncated samples, and to never claim that a draft was executed.

**Errors.** Arguments are validated against `inputSchema` before any endpoint call. Every failure is an `isError` result with `structuredContent.error = {code, http_status, message, hint, retryable}`. The codes are:

- `invalid_arguments`
- `unauthenticated`
- `forbidden`
- `not_found`
- `conflict`
- `upstream_error`
- `unavailable`

**Provenance.** When a proposal cites `publication_keys`, the server stamps the worst-case trust of those publications at draft time. A proposer cannot omit or overstate the trust state of its evidence.

## 4. The operator surface: `/control/agents`

The page is server-rendered through typed `lib/backend.ts` helpers, as ADR §4.3 requires, and has a ControlNav entry. It has four views:

- **Inbox.** For each pending proposal, `GET /api/actions/proposals/{id}/review` provides:
  - what approval does for its adapter (`in_registry_only` vs `release_ha_approval`);
  - a diff-style before → after preview;
  - the cited evidence, with trust at draft time next to trust now, plus lineage and confidence drill-downs;
  - caveats: no evidence, publications missing from the catalog, evidence that is stale now, or evidence drafted while degraded.

  Approve and reject share one recorded reason. A `409`, `403`, `404`, or `502` each gets its own notice.
- **History.** Resolved proposals with their timeline, actors, and reasons.
- **Agents.** Identities observed in the queue (`GET /api/agent/principals`). This view is explicitly not a registry.
- **Tools.** The catalog, showing reads, endpoints, scope, whether a token can reach the tool, and the vuoro operation name.

## 5. vuoro alignment map

Sources: `/projects/dev/vuoro` (vuoro-client 0.1.2 source / 0.1.1 wheel, vuoro-adapter-kit 0.2.2, vuoro-mcp-edge); `/projects/dev/vuoro-cloud` (control plane and `vuoro-cli`, installed as the `vuoro-cloud` uv tool, v0.1.0); `/projects/dev/agentops/docs/contracts/authority-uuid-and-principal-binding.md`.

| Concern | HLA today | vuoro convention | Status |
|---|---|---|---|
| Repo identity | `homelab-analytics.dispatch.json` `authority_repo_uuid` minted locally (`dda443a`, 2026-08-29); `project.toml` `project_id`; no `.vuoro/project.json` | Server-issued immutable authority UUID (target contract); vuoro-cloud `repo bind` takes `repo_id` (`^[a-zA-Z0-9][a-zA-Z0-9._-]{1,127}$`) plus a `vuoro-project/v1` descriptor | **Mismatch.** HLA now reports the UUID as `self-asserted` / `issuer: null` in its manifest. Issuance is a vuoro-side change (5.1). |
| Capability catalog | MCP `tools/list` only | adapter-kit operation spec (`domain.noun.verb`, `execution_semantics`, `idempotency`, `required_authority` `domain:verb`, Draft 2020-12 strict schemas, `catalog_revision` sha256) | **Aligned unilaterally.** `GET /api/agent/manifest` (`hla-agent-capability-manifest/v1`, off by default) |
| Agent registration | None; identities observed from proposals | Proposal only (`docs/plans/2026-10-14-agent-reachability-and-messaging.md`): registered / observed / reachable facts | HLA stays an *observer*. Sessions render the `register_run` shape (`Session.vuoro_run_registration`) without sending it. 5.2 |
| Proposal queue vs work items / effects | `pending / approved / dismissed`, human-only resolution | mcp-edge effect intents `proposed / accepted / rejected / applied / failed`; acceptance by an operator or an opt-in acceptor | **Mapped** in the manifest (`vuoro_effect_state_map`). HLA has no `applied` / `failed` because nothing executes yet. 5.3 |
| Events / inbox | Polling the proposal list | `resource-changes/v1` (`next_cursor`, events) | **Gap.** 5.3 sketches a changes feed. |
| Envelopes / ids | `approval_<hex12>`; agent idempotency key → `agent_<key>` | ULID-prefixed ids; idempotency key `^[A-Za-z0-9._:-]{8,128}$`; `invocation/v1` | Idempotency-key pattern adopted. ULIDs are deferred because the HA routes require the id format to stay stable. |
| Auth | Local / `local_single_user`; Authentik OIDC pending | OAuth PKCE (vuoro-cli), PATs `vuo_pat_*`, authorities `work:*` | Independent. Nothing to align until OIDC lands. |

### 5.1 Proposal to vuoro: issue and validate HLA's authority UUID

Ratify `11318b7d-69cb-4b26-9dfa-1be33d1ea39c` through the agentops migration path (*ratify existing → dual-read → cut*, contract doc §3). Contract sketch for the served side:

```json
POST /api/authority/v1/repositories:ratify
{"schema_version": "authority-ratification/v1",
 "repo_id": "homelab-analytics",
 "claimed_authority_uuid": "11318b7d-69cb-4b26-9dfa-1be33d1ea39c",
 "evidence": {"commit": "dda443a", "descriptor_ref": "homelab-analytics.dispatch.json"}}
→ {"authority_uuid": "...", "status": "ratified", "issuer": "vuoro-shared"}
```

Rejections should use the contract's `repo-unknown`, `repo-unauthorized`, and `repo-unresolvable` codes. Once vuoro returns `issuer`, HLA only changes `HOMELAB_ANALYTICS_AGENT_AUTHORITY_REPO_UUID` handling to report `status: ratified`.

### 5.2 Proposal to vuoro: register published MCP providers, not just runs

The agent-reachability plan covers agents that *do* work. HLA is a *tool provider*. The proposal is that vuoro's directory accept a provider record pointing at a capability manifest:

```json
{"schema_version": "tool-provider-registration/v1",
 "repo_id": "homelab-analytics",
 "manifest_url": "https://<hla>/api/agent/manifest",
 "catalog_revision": "<sha256>",
 "transport": "mcp-stdio",
 "authorities_required": ["hla:read", "hla:propose"]}
```

This would let vuoro's catalog route `hla.*` operations without duplicating HLA's schemas.

### 5.3 Proposal to vuoro: an approval-queue changes feed

HLA would add `GET /api/actions/proposals/changes?cursor=` emitting `resource-changes/v1` (`events[{event_id, terminal, data}]`, where `terminal` is true for approved or dismissed). This is unilateral on the HLA side once the queue is persisted. vuoro would consume it as an effect-intent source, and map `approved` → `accepted` without HLA ever executing on vuoro's behalf.

## 6. AssistantRuntime (Stage B2): design status

The module is `packages/application/use_cases/assistant_runtime.py` and its broker is `apps/agent/assistant_tools.py`.

- **Contract:** `start(context, policy, tools) → Session`, `continue_session(session, input) → Iterator[AssistantEvent]`, `cancel`, and `export_evidence → EvidenceSet`.
- **Boundary duties:**
  - tool grants, with drafts refused unless `allow_drafts`;
  - a tool-call budget;
  - sample-row redaction (on by default);
  - an evidence set that flags `untrusted_citations`;
  - usage counters for provider tokens and cost.
- **Runtimes:** `DeterministicAssistantRuntime` needs no model and no network. It names the best publication and its trust guidance, and never states figures.
- **Gate:** `HOMELAB_ANALYTICS_ASSISTANT_RUNTIME` defaults to `disabled`. `opencode` also requires `HOMELAB_ANALYTICS_ASSISTANT_PROVIDER_CALLS_ALLOWED=true`, and is still refused because no adapter ships.
- **Not wired** to any route.
- **vuoro mapping:** session → `register_run` (`harness_id = hla-assistant/<runtime>`); evidence → `append_evidence`.

## 7. Follow-ups (not in this branch)

1. **Persist the proposal queue** (postgres + sqlite migrations). Wait for the decision-ledger migrations to land, so the two do not collide on migration numbers.
2. **A `proposals:draft` service-token scope**, so an MCP agent token stops needing `admin:write`. This needs the route-policy engine to accept a scope set during migration.
3. **Unify the confidence key namespace** (section 2.5) with the confidence owner.
4. **Retro-shell mirror of `/control/agents`**, read-only, as the policies mirror is.
5. **An OpenCode adapter** behind both gates, once B1 (the deterministic brief) has shipped.

## 8. Open questions

| Question | Options | Recommendation |
|---|---|---|
| How should agents draft policies? | (a) Add a `policies:draft` scope. (b) Drop `propose_policy` from the MCP surface. (c) Keep it reachable only through a machine JWT with explicit permissions. | **(c) now, then (a)** alongside follow-up 7.2. Drafts are already forced disabled, so (a) is safe once the scope exists. |
| Is `/control/agents` admin-only or operator-visible? | (a) Admin-only, as today, matching the other control pages. (b) Operators can see it and resolve proposals. | **(a)** until OIDC groups land. Then move to (b), which needs a route-policy change: generalized `/api/actions/*` mutations currently require `admin.write`, while the HA routes accept `control.action_proposals.write`. Aligning the two is a small `auth_policies.py` change. |
| Publish the manifest by default? | (a) Off, as today. (b) On for `local_single_user`. | **(a)** until 5.2 has a consumer. The manifest is harmless to serve, but nothing reads it yet. |
