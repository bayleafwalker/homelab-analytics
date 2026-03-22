import Link from "next/link";

function publicationSemanticSummary(publication) {
  const measureCount = publication.columns.filter(
    (column) => column.semantic_role === "measure"
  ).length;
  const timeCount = publication.columns.filter(
    (column) => column.semantic_role === "time"
  ).length;
  const statusCount = publication.columns.filter(
    (column) => column.semantic_role === "status"
  ).length;
  const parts = [`${publication.columns.length} fields`];
  if (measureCount > 0) {
    parts.push(`${measureCount} measures`);
  }
  if (timeCount > 0) {
    parts.push(`${timeCount} time`);
  }
  if (statusCount > 0) {
    parts.push(`${statusCount} status`);
  }
  return parts.join(" · ");
}

export function RendererDiscovery({
  title,
  eyebrow,
  descriptors,
  emptyMessage = "No renderer-compatible views were published."
}) {
  if (!descriptors?.length) {
    return (
      <article className="panel section">
        <div className="sectionHeader">
          <div>
            <div className="eyebrow">{eyebrow}</div>
            <h2>{title}</h2>
          </div>
        </div>
        <div className="empty">{emptyMessage}</div>
      </article>
    );
  }

  return (
    <article className="panel section">
      <div className="sectionHeader">
        <div>
          <div className="eyebrow">{eyebrow}</div>
          <h2>{title}</h2>
        </div>
        <span className="statusPill">{descriptors.length} views</span>
      </div>
      <nav className="subnav" aria-label={`${title} navigation`}>
        {descriptors.map((descriptor) => (
          <Link
            key={descriptor.key}
            href={descriptor.href}
            className="subnavLink"
          >
            {descriptor.nav_label}
          </Link>
        ))}
      </nav>
      <div className="cards" style={{ marginTop: "16px", marginBottom: 0 }}>
        {descriptors.map((descriptor) => (
          <section
            key={descriptor.key}
            id={`discovery-${descriptor.anchor}`}
            className="panel metricCard"
            style={{ padding: "20px" }}
          >
            <div className="metricLabel">{descriptor.kind}</div>
            <h3 style={{ margin: "6px 0 8px" }}>{descriptor.nav_label}</h3>
            <div className="muted" style={{ fontSize: "0.92rem", lineHeight: 1.5 }}>
              {descriptor.publications.length > 0
                ? descriptor.publications
                    .map((publication) => publication.display_name)
                    .join(" · ")
                : "No publication contract attached."}
            </div>
            <div
              style={{
                display: "flex",
                flexWrap: "wrap",
                gap: "8px",
                marginTop: "12px",
                marginBottom: "12px"
              }}
            >
              <span className="statusPill">{descriptor.renderMode}</span>
              <span className="statusPill">
                {descriptor.publications.length} publication
                {descriptor.publications.length === 1 ? "" : "s"}
              </span>
            </div>
            <ul
              style={{
                listStyle: "none",
                padding: 0,
                margin: 0,
                display: "grid",
                gap: "10px"
              }}
            >
              {descriptor.publications.map((publication) => (
                <li key={publication.publication_key}>
                  <div style={{ fontWeight: 700 }}>{publication.display_name}</div>
                  <div className="muted" style={{ fontSize: "0.85rem" }}>
                    {publicationSemanticSummary(publication)}
                  </div>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>
    </article>
  );
}
