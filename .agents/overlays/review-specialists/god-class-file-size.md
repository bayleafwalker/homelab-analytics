---
specialist: god-class-file-size
---

## Scope

Detect files, classes, and functions that are too large to review safely. Produce two
outputs: findings for files, classes, or functions that grew in this scope and crossed
a threshold, plus a watchlist of pre-existing top offenders.

Thresholds:

- File: 600 LOC
- Function: about 80 lines
- Class: more than 15 methods, or methods importing from more than three distinct packages

## Calibration anchors

Include any existing production file over 600 LOC in the watchlist, even when it did
not change. Flag growth in `packages/storage/`, `packages/pipelines/`, or a domain
pack when it crosses a threshold and no focused extraction path is evident.

## Severity guidance

- `blocker`: a file grew in this scope and is now more than twice the size of the
  next-largest file in its package.
- `advisory`: a file grew past 600 LOC, or a newly added function crossed 80 lines.
- `watchlist`: an unchanged pre-existing offender.

Return `[]` when no findings apply.