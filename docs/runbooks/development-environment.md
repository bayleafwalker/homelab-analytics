# Reproducible development environment

Each checkout owns its Python virtual environment, Node runtime, frontend
dependencies, and Next.js output. Prepare them from the checkout root:

```sh
make dev-setup
```

Setup runs `uv sync --locked --extra dev` from `uv.lock`, bootstraps the pinned
Node.js 20.20.1 Linux x64 archive when needed, verifies its SHA-256 against the
[Node.js release checksum](https://nodejs.org/en/blog/release/v20.20.1), then
runs `npm ci` from the committed frontend lock. It records the checksum-verified
archive identity beside the runtime; later commands reject runtimes without
that provenance marker or whose files resolve outside the checkout.
The Node runtime is stored in `.tooling/`; Python packages use `.venv/`; frontend
packages use `apps/web/frontend/node_modules/`. These are ignored, checkout-local
directories and are never shared with another checkout. Package-manager write
caches are also kept under `.tooling/` so warm setup does not require writes to a
user-wide cache.

After setup, focused development checks run independently of the setup shell:

```sh
make dev-check
```

This establishes the owned Node and measured DuckDB loader environment in that
command, performs a bounded FastAPI `TestClient` and local event-loop probe, runs
the existing Ruff and non-slow pytest checks, then runs frontend token,
transport-contract, and TypeScript checks. A TestClient probe timeout fails
before the suite with environment guidance; it does not skip or alter tests.
For an actionable missing-dependency error, run `make dev-setup` first.

To build and exercise the standalone web target on loopback, run:

```sh
make dev-smoke
```

The smoke command starts an owned loopback stub that returns only a synthetic
503 response, uses it as the API base for both the Next build and app runtime,
builds Next.js, places static assets beside the existing standalone server
entrypoint, launches the app on a temporary loopback port, fetches the rendered
page, and fetches one referenced `/_next/static/` asset. It ignores inherited
HLA backend and identity variables. The server and stub process groups are
settled with bounded TERM then KILL cleanup, including on cancellation. The first
setup needs network access to the Python package index, npm registry, and Node.js
release archive.
If setup reports an unavailable package or native `esbuild` executable, retain
the full installer output; the command does not skip or relax those checks.
