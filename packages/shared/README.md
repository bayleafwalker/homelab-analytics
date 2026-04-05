# Shared Package

Cross-cutting types, settings, logging, and utility helpers shared across apps and packages.

Current foundation:

- environment-based application settings for landing storage, metadata storage, and API bind configuration
- derived inbox, processed, failed, and worker poll settings for the current folder-based ingestion loop
- extension registry and module loading helpers for built-in and externally mounted landing, transformation, reporting, and application code
- executable extension hooks for worker- and API-invoked landing, transformation, and reporting flows
