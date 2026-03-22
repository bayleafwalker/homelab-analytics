# Publication Contracts

Publication contracts are the backend-owned semantic surface for renderer consumers.

The API exports them through:

- `GET /contracts/publications`
- `GET /contracts/publications/{publication_key}`
- `GET /contracts/ui-descriptors`

The committed frontend artifacts are generated from the same export path:

- `apps/web/frontend/generated/publication-contracts.json`
- `apps/web/frontend/generated/publication-contracts.ts`

## Contract model

Each publication contract exposes:

- `publication_key`: stable consumer-facing identity
- `relation_name`: backing reporting relation or current-dimension view
- `schema_name`: publication schema identifier
- `schema_version`: semantic contract version for renderer compatibility
- `display_name` and `description`: human-facing metadata
- `pack_name` and `pack_version`: owning capability-pack provenance when applicable
- `visibility`, `retention_policy`, and `lineage_required`: publication governance metadata
- `supported_renderers`, `renderer_hints`, and `ui_descriptor_keys`: renderer discovery metadata
- `columns`: ordered column contracts

Each column contract exposes:

- `name`, `storage_type`, `json_type`, and `nullable`: transport and storage shape
- `description`: renderer-facing field meaning
- `semantic_role`: one of `identifier`, `dimension`, `time`, `measure`, or `status`
- `unit`: optional semantic unit such as `currency`, `percent`, `bytes`, or `count`
- `grain`: optional time grain such as `timestamp`, `day`, or `month`
- `aggregation`: optional measure behavior such as `sum`, `avg`, `count`, `latest`, or `pct_change`
- `filterable` and `sortable`: default renderer affordances

## Authoring rules

Built-in capability-pack publications are expected to declare full field semantics in the pack manifest.

That means every pack-owned publication should provide:

- `schema_version`
- one semantic definition for every exported field in the backing publication relation

The export pipeline rejects pack-owned publications when:

- a semantic definition references a column that does not exist in the reporting relation
- a reporting column is missing semantic metadata

Internal non-pack relations still export with inferred fallback semantics so contract discovery stays complete, but pack-owned publications are the strict semantic boundary that renderers should prefer.

## Renderer guidance

Renderers should treat publication contracts as the source of truth for:

- whether a field is a time axis, grouping dimension, status indicator, or numeric measure
- whether values should be handled as currency, percent, bytes, or generic counts
- whether a field should be filterable or sortable by default
- which UI descriptors and renderers are associated with a publication

Renderers should not infer meaning from relation names, page routes, or backend implementation details when the publication contract already declares it.

### Current web renderer hints

Built-in UI descriptors that support the web renderer currently use these `renderer_hints` keys:

- `web_surface`: which aggregate web surface owns the view today, for example `overview`, `reports`, or `homelab`
- `web_render_mode`: whether the current shell renders a dedicated detail section (`detail`) or only discovery metadata (`discovery`)
- `web_anchor`: stable in-page anchor used by the renderer discovery navigation

### Current Home Assistant renderer hints

Built-in publications that support the Home Assistant renderer currently use these `renderer_hints` keys:

- `ha_object_id`: MQTT discovery object id for the rendered sensor
- `ha_entity_name`: Home Assistant-facing entity name
- `ha_state_aggregation`: aggregation strategy over publication rows, currently `count`, `sum`, `latest`, or `max`
- `ha_state_field`: optional publication field used by non-count aggregations
- `ha_filter_field` and `ha_filter_values`: optional row filter applied before aggregation
- `ha_icon`, `ha_unit`, and `ha_device_class`: optional MQTT discovery metadata

The HA MQTT publisher is expected to consume these hints through the same publication and UI descriptor contract export used by the web renderer. HA-enabled publications should therefore opt in through both:

- publication renderer hints that describe how to summarize the publication into an HA entity
- at least one UI descriptor whose `supported_renderers` includes `ha`

## Frontend usage

The generated TypeScript helper types in `apps/web/frontend/generated/publication-contracts.ts` include:

- `PublicationContractMap`
- `PublicationKey`
- `PublicationContractFor<Key>`
- `PublicationColumnsFor<Key>`
- `PublicationColumnName<Key>`
- `PublicationColumnContractFor<Key, ColumnName>`
- `PublicationRowMap`
- `UiDescriptorMap`
- `UiDescriptorKey`

Those types are intended to support renderer logic without hand-maintained publication DTO mirrors.
