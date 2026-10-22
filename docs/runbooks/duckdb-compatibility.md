# DuckDB compatibility

**Classification:** CROSS-CUTTING

## Current source baseline

`pyproject.toml` pins DuckDB to **1.5.1**, matching the existing `uv.lock`
resolution. The shared Python image used by the API and worker installs with
`pip install .`; it does not consume `uv.lock`. CI also installs the project
through pip. An exact project dependency keeps those installations on the same
engine as locked development. The web image is a separate Node/Next.js image.

This is a reproducibility baseline, not an assertion about the running image or
the version that created an existing warehouse. Merging the pin does not change
a deployed image, rewrite a database, or authorize a downgrade. The image
publication workflow runs on version tags or an explicit manual dispatch;
ordinary source merges do not publish a release.

DuckDB's [2.0 announcement](https://duckdb.org/2026/10/21/announcing-duckdb-200)
states that files created by 2.0 cannot be read by earlier engines. It also
states that 2.0 can read and write existing older files while retaining their
older readability, and recommends testing on a shadow system first. File
provenance therefore matters: the currently installed engine alone does not
identify a warehouse's format. The same announcement extends 1.5 support to
March 2027. Reassess the pin in a separately verified engine change; it is not a
permanent version policy. Source checked on 22 October 2026.

## Before deploying a newly built image

Record the following for the API and worker separately:

| Evidence | Required detail |
| --- | --- |
| Running image | Actual image digest and source commit, supplied by the operator's runtime inventory; a GitOps manifest shows desired state only. |
| Engine | Imported `duckdb.__version__` from that exact image. |
| Warehouse provenance | Creation/rebuild history, engine used, file/WAL location and latest verified backup. Mark unknown history explicitly. |
| Restore baseline | Image digest and backup pair that passed a restore drill, plus application migration heads. |

An operator can inspect a known image without mounting any warehouse or passing
production credentials:

```bash
# Set this to the actual immutable Python image reference from the inventory.
ANALYTICS_IMAGE='ghcr.io/bayleafwalker/homelab-analytics@sha256:<recorded-digest>'
docker run --rm --network none --entrypoint python "$ANALYTICS_IMAGE" \
  -c 'import duckdb; print(duckdb.__version__)'
```

If the running engine is newer than this source baseline, do not deploy the
1.5.1 build until compatibility with a retained copy is established. If a
warehouse was created by 2.0, or creation history is unknown, stop any proposed
downgrade. Preserve the existing compatible image and data. Plan either a
verified rebuild from retained inputs or a separately checked logical migration;
installing an older Python package does not convert a database format.

## Engine upgrade procedure

1. **Fix the candidate scope.** Choose one exact target engine and its matching
   extension versions on an upgrade branch. Update the project pin and lock
   together. Record the old and candidate image digests. Keep application
   behavior and schema changes separate where practical so output differences
   have an identifiable cause.
2. **Capture a recoverable baseline.** Follow
   [backup and restore](backup-and-restore.md), including writer coordination,
   warehouse/WAL consistency, separate Postgres and object-storage coverage, and
   an off-site copy. Run the existing `verify-backup` and `restore-drill` with the
   recorded baseline image. Checksums and application migration heads alone do
   not establish engine-format compatibility.
3. **Create isolated shadow inputs.** Use independently restored copies for the
   baseline and candidate. Never point both versions at the same warehouse or
   let either shadow connect to production outputs. Remove production
   credentials and scheduled effects from the shadow environment. Keep the
   untouched baseline backup outside both writable shadow paths.
4. **Exercise both file histories.** Test the candidate against a copy of an
   existing warehouse and against a freshly rebuilt warehouse. The second case
   reveals format or default changes hidden by an older file. Include
   application migrations, representative ingestion, transformation, published
   reporting and backup/restore behavior.
5. **Compare outcomes.** Compare logical schemas, row identities, null handling,
   decimal values, timestamps, category assignments and representative reporting
   outputs against independently specified expectations. Define any numerical
   tolerances before the run. Record counts and totals, but do not treat them as
   sufficient evidence of semantic equivalence. Check timing and resource use
   where those affect the operating workload.
6. **Prove the recovery route.** Restore the untouched baseline backup into
   scratch using its recorded image. If the plan claims an in-place engine
   rollback, separately demonstrate that the old image can read a disposable
   copy of the post-candidate file and supports the candidate's schema and
   extension usage. A newly created 2.0-format file has no 1.x binary rollback;
   recovery must use the retained baseline or a separately verified conversion.
7. **Review and deploy through GitOps.** Attach the comparison and restore
   results to the upgrade PR, run the repository gates below, and obtain the
   normal review. Release/publish and the `appservice` image change are separate
   operator actions. Coordinate API and worker images and writers; do not mix
   unverified engines against a shared file.

Stop the upgrade if outputs differ without an accepted explanation, a required
extension is unavailable, concurrent access differs, or the recovery route
fails. Retain both the candidate results and the untouched recoverable baseline.

## Repository gates

The metadata test derives the required version from the exact project
declaration, compares it with the lock's resolved engine and root dependency
metadata, and checks the imported runtime. Removing the pin or allowing either
installation path to drift fails that check.

```bash
make test-target TEST="tests/test_project_metadata.py tests/test_duckdb_migration.py tests/test_duckdb_path_lineage.py tests/test_worker_backup_restore.py -x --tb=short"
make verify-fast
```

These repository checks use synthetic or temporary data. They do not replace
the shadow and restore evidence for the actual deployment. Follow
[release governance](release-governance.md) for any later image publication.
