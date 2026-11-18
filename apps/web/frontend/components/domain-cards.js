import Link from "next/link";
import { formatMoney, formatMonth } from "@/lib/format";

const DOMAINS = {
  finance: {
    name: "Finance",
    metric: "Latest monthly net cashflow",
    empty: "No cashflow observations yet.",
  },
  utilities: {
    name: "Utilities",
    metric: "Latest monthly billed costs",
    empty: "No billed utility costs observed.",
  },
  homelab: {
    name: "Homelab",
    metric: "Unhealthy services",
    empty: "No service health observations yet.",
  },
};

const observedAt = new Intl.DateTimeFormat("en-GB", {
  dateStyle: "medium",
  timeStyle: "short",
  timeZone: "UTC",
});

function MetricPoint({ point }) {
  const serviceMetric = point.unit === "services";
  return (
    <>
      <strong>
        {serviceMetric
          ? `${point.value} ${point.value === 1 ? "service" : "services"}`
          : `${point.unit} ${formatMoney(point.value, null)}`}
      </strong>
      {" · "}
      <time dateTime={point.period}>
        {serviceMetric ? `${observedAt.format(new Date(point.period))} UTC` : formatMonth(point.period)}
      </time>
      {serviceMetric && point.known_count != null && (
        <span className="muted"> · {point.known_count} with known health</span>
      )}
    </>
  );
}

function DomainCard({ card }) {
  const { name, metric, empty } = DOMAINS[card.domain_key];
  const id = `domain-card-${card.domain_key}`;
  const trendUnits = [...new Set(card.trend.map((point) => point.unit))];
  return (
    <article className="panel section compactStack" aria-labelledby={id}>
      <h3 id={id}>{name}</h3>
      <div>
        <h4>{metric}</h4>
        {card.metric_state === "available" ? (
          <ul>
            {card.headline.map((point) => (
              <li key={point.unit}><MetricPoint point={point} /></li>
            ))}
          </ul>
        ) : (
          <p className="muted">{card.metric_state === "empty" ? empty : "Metric unavailable."}</p>
        )}
      </div>
      <div>
        <h4>Trend</h4>
        {card.trend_state === "available" ? (
          trendUnits.map((unit) => (
            <ol key={unit} aria-label={`${name} trend in ${unit}`}>
              {card.trend.filter((point) => point.unit === unit).map((point) => (
                <li key={point.period}><MetricPoint point={point} /></li>
              ))}
            </ol>
          ))
        ) : (
          <p className="muted">
            {card.trend_state === "insufficient_history"
              ? "No comparable history yet." : "Trend unavailable."}
          </p>
        )}
      </div>
      <div>
        <h4>Top attention</h4>
        {card.attention ? (
          <Link className="inlineLink" href={card.attention.href}>{card.attention.label}</Link>
        ) : (
          <p className="muted">
            {card.attention_state === "empty" ? "Nothing needs attention." : "Attention unavailable."}
          </p>
        )}
      </div>
    </article>
  );
}

export function DomainCards({ cards }) {
  return (
    <section aria-labelledby="domain-cards-heading">
      <h2 id="domain-cards-heading">Domain cards</h2>
      {cards ? (
        <div className="cards">
          {cards.map((card) => <DomainCard key={card.domain_key} card={card} />)}
        </div>
      ) : (
        <p className="muted">Domain cards unavailable.</p>
      )}
    </section>
  );
}
