# Docker Assets

Container build files and local development container definitions belong here.

Current foundation:

- `Dockerfile` installs the Python package and starts the API by default
- `web.Dockerfile` builds the standalone Next.js web workload
- `.dockerignore` keeps local caches, tests, docs, and virtualenv state out of the image build context
