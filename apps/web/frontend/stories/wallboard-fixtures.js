// Shared wallboard fixtures shaped like the /api/wallboard/* responses.

export const NOW = "2026-10-18T07:42:00";

export const servicesData = {
  available: true,
  generated_at: "2026-10-18T07:42:00+00:00",
  services: [
    { service_id: "backup", name: "Backups", host: "nas", status: "degraded", state: "degraded", uptime_seconds: 5400, cpu_pct: null, mem_gb: null, metrics_window: null, recorded_at: "2026-10-18T07:40:00+00:00", stale: false },
    { service_id: "ha", name: "Home Assistant", host: "nuc", status: "up", state: "running", uptime_seconds: 1209600, cpu_pct: 6.4, mem_gb: 1.2, metrics_window: "7d_avg", recorded_at: "2026-10-18T07:40:00+00:00", stale: false },
    { service_id: "nas", name: "NAS", host: "nas", status: "up", state: "running", uptime_seconds: 3801600, cpu_pct: 2.1, mem_gb: 3.8, metrics_window: "7d_avg", recorded_at: "2026-10-18T07:40:00+00:00", stale: false },
    { service_id: "grafana", name: "Grafana", host: "nuc", status: "up", state: "running", uptime_seconds: 86400, cpu_pct: null, mem_gb: null, metrics_window: null, recorded_at: "2026-10-17T21:00:00+00:00", stale: true },
  ],
};

export const devicesData = {
  available: true,
  generated_at: "2026-10-18T07:42:00+00:00",
  rooms: [
    { room: "bedroom", temperature_c: 19.8, humidity_pct: 48, power_w: null, sensor_count: 2, last_seen: "2026-10-18T07:40:00+00:00" },
    { room: "kitchen", temperature_c: null, humidity_pct: null, power_w: 410, sensor_count: 2, last_seen: "2026-10-18T07:41:00+00:00" },
    { room: "living_room", temperature_c: 21.4, humidity_pct: 44, power_w: 152, sensor_count: 4, last_seen: "2026-10-18T07:41:00+00:00" },
  ],
};

export const eventsData = {
  since: "2026-10-17T19:42:00+00:00",
  generated_at: "2026-10-18T07:42:00+00:00",
  sources: { runs: true, proposals: true, alerts: true },
  events: [
    { event_id: "alert:budget:1", kind: "alert", at: "2026-10-18T07:30:00+00:00", title: "Alert: Budget (breach)", detail: null, tone: "warn" },
    { event_id: "proposal:p1:approved", kind: "proposal", at: "2026-10-18T06:55:00+00:00", title: "Approved: Charge battery overnight", detail: "operator", tone: "ok" },
    { event_id: "run:r1", kind: "ingestion", at: "2026-10-18T06:00:00+00:00", title: "Ingested transactions", detail: "42 rows from bank", tone: "ok" },
    { event_id: "run:r2", kind: "ingestion", at: "2026-10-18T03:10:00+00:00", title: "Ingestion rejected: bills", detail: "0 rows from upload", tone: "warn" },
    { event_id: "proposal:p1:created", kind: "proposal", at: "2026-10-17T22:15:00+00:00", title: "Proposed: Charge battery overnight", detail: "Cheap hours 01-05", tone: "neutral" },
  ],
};

function hourIso(offset) {
  const start = Date.UTC(2026, 9, 17, 8) + offset * 3600000;
  return new Date(start).toISOString().replace(".000Z", "+00:00");
}

const KWH = [0.42, 0.38, 0.35, 0.31, 0.6, 0.9, 1.2, 1.4, 1.1, 0.8, 0.7, null, null, 0.5, 0.45, 0.4, 0.38, 0.36, 0.52, 0.8, 1.6, 2.1, 1.3, 0.4];

export const powerData = {
  available: true,
  status: "ok",
  window_hours: 24,
  unit: "kWh",
  generated_at: "2026-10-18T07:42:00+00:00",
  meter: { entity_id: "sensor.house_energy", name: "House energy", unit: "kWh" },
  candidates: [{ entity_id: "sensor.house_energy", name: "House energy", unit: "kWh" }],
  total_kwh: 17.7,
  buckets: KWH.map((kwh, index) => ({
    hour_start: hourIso(index),
    hour_end: hourIso(index + 1),
    kwh,
    partial: index === KWH.length - 1,
  })),
};

export const powerAmbiguous = {
  ...powerData,
  status: "ambiguous",
  meter: null,
  total_kwh: null,
  candidates: [
    { entity_id: "sensor.plug_energy", name: "Plug", unit: "kWh" },
    { entity_id: "sensor.ev_energy", name: "EV", unit: "kWh" },
  ],
  buckets: powerData.buckets.map((bucket) => ({ ...bucket, kwh: null })),
};
