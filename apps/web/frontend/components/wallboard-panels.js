import React from "react";

// Wallboard panels fed by the /api/wallboard/* adapters. Each takes the
// adapter payload as-is (or null when the adapter could not be reached) and
// renders an honest "not connected" / "unknown" state instead of zeros.

const STATUS_LABEL = { up: "Up", degraded: "Degraded", down: "Down", unknown: "Unknown" };
const STATUS_TONE = { up: "ok", degraded: "warn", down: "warn", unknown: "muted" };

function formatUptime(seconds) {
  if (seconds == null) return "uptime unknown";
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  if (days > 0) return `up ${days}d ${hours}h`;
  const minutes = Math.floor((seconds % 3600) / 60);
  return hours > 0 ? `up ${hours}h ${minutes}m` : `up ${minutes}m`;
}

function utcHour(iso) {
  return String(iso || "").slice(11, 13);
}

function timeOfDay(iso) {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
}

function roomLabel(room) {
  if (!room) return "No room";
  return room.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
}

function Panel({ label, area, tone = "neutral", children, note = null }) {
  return (
    <section className="wallPanel" data-area={area} data-tone={tone} aria-label={label}>
      <h2 className="wallTileLabel">
        {label}
        {note ? <span className="wallPanelNote"> {note}</span> : null}
      </h2>
      {children}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Services
// ---------------------------------------------------------------------------

export function ServiceTile({ service }) {
  const status = service.stale && service.status === "up" ? "unknown" : service.status;
  const metrics = [];
  if (service.cpu_pct != null) metrics.push(`cpu ${service.cpu_pct}%`);
  if (service.mem_gb != null) metrics.push(`mem ${service.mem_gb} GB`);
  return (
    <li className="wallService" data-tone={STATUS_TONE[status] || "muted"}>
      <span className="wallServiceStatus">{STATUS_LABEL[status] || "Unknown"}</span>
      <span className="wallServiceName">{service.name}</span>
      <span className="wallServiceMeta">
        {service.host ? `${service.host} · ` : ""}
        {formatUptime(service.uptime_seconds)}
        {service.stale ? " · stale reading" : ""}
      </span>
      <span className="wallServiceMetrics">
        {metrics.length ? `${metrics.join(" · ")} (7d avg)` : "cpu/mem unknown"}
      </span>
    </li>
  );
}

export function ServicesPanel({ data }) {
  const services = data?.services || [];
  if (!data || data.available === false) {
    return (
      <Panel label="Services" area="services" tone="muted">
        <p className="wallBig wallQuiet">Not connected</p>
        <p className="wallLine">Service health needs the homelab reporting marts.</p>
      </Panel>
    );
  }
  if (services.length === 0) {
    return (
      <Panel label="Services" area="services" tone="muted">
        <p className="wallBig wallQuiet">No services reporting</p>
        <p className="wallLine">Connect the homelab bridge to see service health here.</p>
      </Panel>
    );
  }
  const up = services.filter((row) => row.status === "up" && !row.stale).length;
  const bad = services.some((row) => row.status === "down" || row.status === "degraded");
  return (
    <Panel label="Services" area="services" tone={bad ? "warn" : "ok"} note={`${up}/${services.length} up`}>
      <ul className="wallServices">
        {services.slice(0, 8).map((service) => (
          <ServiceTile key={service.service_id || service.name} service={service} />
        ))}
      </ul>
      {services.length > 8 ? <p className="wallLine">and {services.length - 8} more</p> : null}
    </Panel>
  );
}

// ---------------------------------------------------------------------------
// Devices
// ---------------------------------------------------------------------------

function Reading({ value, unit, label }) {
  return (
    <span className="wallReading">
      <span className="wallReadingValue">{value == null ? "—" : `${value}${unit}`}</span>
      <span className="wallReadingLabel">{value == null ? `${label} unknown` : label}</span>
    </span>
  );
}

export function DevicePanel({ data }) {
  const rooms = data?.rooms || [];
  if (!data || data.available === false) {
    return (
      <Panel label="Rooms" area="devices" tone="muted">
        <p className="wallBig wallQuiet">Not connected</p>
        <p className="wallLine">Room readings come from the Home Assistant bridge.</p>
      </Panel>
    );
  }
  if (rooms.length === 0) {
    return (
      <Panel label="Rooms" area="devices" tone="muted">
        <p className="wallBig wallQuiet">No room sensors</p>
        <p className="wallLine">No temperature, humidity or power sensors seen yet.</p>
      </Panel>
    );
  }
  return (
    <Panel label="Rooms" area="devices">
      <ul className="wallRooms">
        {rooms.slice(0, 6).map((room) => (
          <li key={room.room || "_none"} className="wallRoom">
            <span className="wallRoomName">{roomLabel(room.room)}</span>
            <Reading value={room.temperature_c} unit="°" label="temp" />
            <Reading value={room.humidity_pct} unit="%" label="humidity" />
            <Reading value={room.power_w} unit=" W" label="power" />
          </li>
        ))}
      </ul>
    </Panel>
  );
}

// ---------------------------------------------------------------------------
// Event feed
// ---------------------------------------------------------------------------

const KIND_LABEL = { ingestion: "data", proposal: "action", alert: "alert" };

export function EventFeed({ data, limit = 8 }) {
  if (!data) {
    return (
      <Panel label="Events" area="events" tone="muted">
        <p className="wallBig wallQuiet">Not connected</p>
      </Panel>
    );
  }
  const events = data.events || [];
  const missing = Object.entries(data.sources || {})
    .filter(([, wired]) => !wired)
    .map(([name]) => name);
  const note = missing.length ? `(no ${missing.join(", ")})` : null;
  if (events.length === 0) {
    return (
      <Panel label="Events, last 12h" area="events" tone="muted" note={note}>
        <p className="wallBig wallQuiet">Quiet</p>
        <p className="wallLine">No runs, proposals or alerts since {timeOfDay(data.since)}.</p>
      </Panel>
    );
  }
  return (
    <Panel
      label="Events, last 12h"
      area="events"
      tone={events.some((event) => event.tone === "warn") ? "warn" : "neutral"}
      note={note}
    >
      <ol className="wallEvents">
        {events.slice(0, limit).map((event) => (
          <li key={event.event_id} className="wallEvent" data-tone={event.tone}>
            <time className="wallEventTime" dateTime={event.at}>
              {timeOfDay(event.at)}
            </time>
            <span className="wallEventKind">{KIND_LABEL[event.kind] || event.kind}</span>
            <span className="wallEventTitle">
              {event.title}
              {event.detail ? <span className="wallEventDetail"> {event.detail}</span> : null}
            </span>
          </li>
        ))}
      </ol>
    </Panel>
  );
}

// ---------------------------------------------------------------------------
// Power, 24 UTC hours
// ---------------------------------------------------------------------------

const CHART_W = 480;
const CHART_H = 140;
const BAR_GAP = 3;

function powerSummary(buckets, total) {
  const known = buckets.filter((bucket) => bucket.kwh != null);
  if (!known.length) return "No energy readings in this window.";
  const peak = known.reduce((best, bucket) => (bucket.kwh > best.kwh ? bucket : best), known[0]);
  const unknown = buckets.length - known.length;
  return (
    `${total} kWh over ${buckets.length} hours; peak ${peak.kwh} kWh at ${utcHour(peak.hour_start)}:00 UTC` +
    (unknown ? `; ${unknown} hours unknown.` : ".")
  );
}

export function PowerChart({ data }) {
  if (!data || data.available === false) {
    return (
      <Panel label="Energy, 24h" area="power" tone="muted">
        <p className="wallBig wallQuiet">Not connected</p>
        <p className="wallLine">Hourly energy comes from the Home Assistant bridge.</p>
      </Panel>
    );
  }
  if (data.status !== "ok") {
    return (
      <Panel label="Energy, 24h" area="power" tone="muted">
        <p className="wallBig wallQuiet">{data.status === "ambiguous" ? "Choose a meter" : "No energy meter"}</p>
        <p className="wallLine">
          {data.status === "ambiguous"
            ? `${data.candidates.length} energy meters found and none is marked as the house meter.`
            : "No kWh sensor is reporting through the bridge."}
        </p>
      </Panel>
    );
  }
  const buckets = data.buckets || [];
  const max = Math.max(0.001, ...buckets.map((bucket) => bucket.kwh || 0));
  const barW = buckets.length ? CHART_W / buckets.length : CHART_W;
  const summary = powerSummary(buckets, data.total_kwh);
  return (
    <Panel label="Energy, 24h" area="power" note={data.meter?.name || data.meter?.entity_id}>
      <p className="wallBig">{data.total_kwh == null ? "Unknown" : `${data.total_kwh} kWh`}</p>
      <svg
        className="wallPower"
        viewBox={`0 0 ${CHART_W} ${CHART_H + 26}`}
        role="img"
        aria-label={`Energy use by hour. ${summary}`}
      >
        {buckets.map((bucket, index) => {
          const x = index * barW + BAR_GAP / 2;
          const w = Math.max(1, barW - BAR_GAP);
          if (bucket.kwh == null) {
            return <rect key={bucket.hour_start} className="wallPowerUnknown" x={x} y={CHART_H - 3} width={w} height={3} />;
          }
          const h = Math.max(2, (bucket.kwh / max) * (CHART_H - 8));
          return (
            <rect
              key={bucket.hour_start}
              className="wallPowerBar"
              data-partial={bucket.partial}
              x={x}
              y={CHART_H - h}
              width={w}
              height={h}
            />
          );
        })}
        {buckets.map((bucket, index) =>
          index % 6 === 0 ? (
            <text key={`l-${bucket.hour_start}`} className="wallPowerAxis" x={index * barW + 2} y={CHART_H + 22}>
              {utcHour(bucket.hour_start)}
            </text>
          ) : null
        )}
      </svg>
      <p className="wallLine">Hours in UTC. Dashes are hours with no reading.</p>
    </Panel>
  );
}
