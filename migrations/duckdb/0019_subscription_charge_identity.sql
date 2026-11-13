-- Existing marts have no reliable mapping to a charge; rebuild them from facts.
ALTER TABLE mart_subscription_summary ADD COLUMN IF NOT EXISTS charge_id VARCHAR;
ALTER TABLE mart_upcoming_fixed_costs_30d ADD COLUMN IF NOT EXISTS charge_id VARCHAR;
