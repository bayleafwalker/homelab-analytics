# Release Governance

## Purpose

This runbook defines the repository policy for branch lifetime, tag usage, and GitHub Releases.

Use it with `docs/runbooks/project-working-practices.md` for the execution loop and `docs/agents/release-ops.md` for verification expectations.

## Branch Policy

- `main` is the only long-lived branch.
- Feature, fix, and agent branches are temporary execution branches and must start from `main`.
- Merge work back to `main`, then delete the branch locally and remotely.
- GitHub merged-branch auto-delete must remain enabled unless a documented exception requires otherwise.
- Do not keep remote branches as archival markers. Use tags for durable checkpoints.

## Tag Policy

Tags exist for two different purposes: product releases and sprint checkpoints.

### Version Tags

Use semantic version tags for product milestones:

```text
v0.1.0
v0.2.0
v1.0.0
```

Rules:
- version tags must be annotated tags
- version tags must point to a commit already reachable from `main`
- every version tag must have a matching published GitHub Release
- version tags are the only tags that should drive public publish-on-tag automation

### Sprint Tags

Use sprint tags for shipped checkpoint references:

```text
sprint/a-homelab-pack
sprint/e2-expense-shock
sprint/ha-phase5
```

Rules:
- sprint tags must be annotated tags going forward
- sprint tags mark shipped checkpoints only; they do not get a GitHub Release
- sprint tags should point to the merge commit on `main` when the sprint shipped through a PR
- if a sprint shipped without a PR, tag the final pushed commit that represents the shipped checkpoint

### Legacy Tags

Older lightweight sprint tags remain valid historical references.

Do not rewrite or delete historical sprint tags just to normalize their tag type. The policy change applies going forward.

## When To Cut A Version

Do not create a version for every sprint.

Create a semantic version only when a coherent user-facing milestone ships, such as:
- a new installable or operable product baseline
- a materially expanded capability surface that changes what the platform can do
- a release that needs explicit migration, deprecation, or compatibility notes

Use sprint tags for ordinary delivery checkpoints that do not represent a new product milestone.

## GitHub Release Policy

Every semantic version release must publish a GitHub Release on the matching `v*` tag.

The release body should include:
- the user-facing scope of the milestone
- notable operational or deployment changes
- migration or deprecation notes when relevant
- verification summary for the release cut
- references to generated contract artifacts or compatibility summaries when contracts changed

Sprint tags do not create GitHub Releases.

## Minimum Release Checklist

Before creating a semantic version tag or GitHub Release:
- the target commit is already on `main`
- `make verify-fast` passes
- docs and requirements reflect the shipped behavior
- contract changes have a reviewed compatibility summary when applicable
- Docker, Helm, or deployment verification is run when the release changes those surfaces

Suggested commands:

```bash
# version milestone
git tag -a v0.2.0 -m "v0.2.0 - <milestone title>"
git push origin v0.2.0
gh release create v0.2.0 --verify-tag --generate-notes

# sprint checkpoint
git tag -a sprint/ha-phase6 -m "Sprint HA Phase 6 - approval queue"
git push origin sprint/ha-phase6
```

## Repo Defaults

Repo settings should reinforce the policy:
- merged branches auto-delete on GitHub
- release automation, when enabled, keys off `v*` tags rather than `sprint/*` tags
- historical checkpoint tracking lives in tags and docs, not in preserved topic branches
