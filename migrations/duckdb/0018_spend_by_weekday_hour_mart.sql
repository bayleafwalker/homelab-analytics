-- 0018_spend_by_weekday_hour_mart: reporting mart behind the spend heatmap
-- (GET /reports/spend-heatmap). One row per booking date and UTC hour bucket,
-- rebuilt via DELETE + INSERT on refresh from fact_transaction_current, with
-- the time of day borrowed from fact_transaction. hour_of_day is NULL for
-- bookings whose source carried a date but no time of day.

CREATE TABLE IF NOT EXISTS mart_spend_by_weekday_hour (
    booked_at DATE NOT NULL,
    day_of_week INTEGER NOT NULL,
    hour_of_day INTEGER,
    total_expense DECIMAL(18,4) NOT NULL,
    transaction_count INTEGER NOT NULL
);
