# Training Artifacts

**Classification:** CROSS-CUTTING

## Purpose

This directory holds committed, curated training artifacts derived from real sessions, reviews, and workflow experiments.

Use it for reusable examples that teach future agents or engineers how a workflow should run, where it failed, and what made it succeed.

## Relationship To Other Surfaces

- `.agents/sessions/` holds raw session history and execution notes.
- `docs/knowledge/knowledge-base.md` holds concise durable knowledge published through `kctl`.
- `docs/training/` holds curated narrative examples where chronology, command sequence, tradeoffs, and workflow assessment matter.
- `docs/notes/` remains the right place for out-of-scope idea capture that is not yet accepted work and not mature enough to become training.

## What belongs here

- worked workflow examples
- post-session workflow suitability assessments
- reusable troubleshooting sequences
- agent-coordination examples with stable lessons
- curated training material derived from `.agents/sessions/`

## What does not belong here

- raw prompt dumps
- full terminal transcripts with no curation
- speculative ideas that have not been shaped into a reusable lesson
- duplicated knowledge that should instead be a short `kctl` publication

## Authoring rules

- Keep the source session note referenced explicitly.
- Preserve only the commands, errors, and decisions that teach something reusable.
- Sanitize anything that should not become a durable repo artifact.
- Prefer dated files when the artifact is a session-derived example.
- Use `workflow-artifact-TEMPLATE.md` for new workflow training notes unless another family-specific template exists.
