-- Register service health observation batches for publication from Homelab.

INSERT INTO publication_definitions (
    publication_definition_id,
    transformation_package_id,
    publication_key,
    name,
    description,
    archived,
    created_at
)
VALUES (
    'pub_homelab_service_health_history',
    'builtin_homelab',
    'mart_service_health_history',
    'Service health observation batches',
    NULL,
    FALSE,
    NOW()
)
ON CONFLICT (publication_definition_id) DO NOTHING;
