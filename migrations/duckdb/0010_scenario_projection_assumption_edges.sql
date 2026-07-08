CREATE TABLE IF NOT EXISTS fact_scenario_projection_assumption_edge (
    scenario_id VARCHAR NOT NULL,
    projection_table VARCHAR NOT NULL,
    projection_row_key VARCHAR NOT NULL,
    assumption_key VARCHAR NOT NULL
);
