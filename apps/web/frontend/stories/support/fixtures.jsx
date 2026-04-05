import React from "react";

export const readerUser = {
  username: "reader",
  role: "reader",
};

export const operatorUser = {
  username: "operator",
  role: "operator",
};

export const adminUser = {
  username: "admin",
  role: "admin",
};

export const sparklineLabels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"];

export const sparklineSeries = [
  {
    label: "Cashflow",
    color: "var(--accent)",
    values: [920, 1180, 1040, 1325, 1260, 1420],
  },
  {
    label: "Baseline",
    color: "var(--accent-warm)",
    values: [980, 1000, 1010, 1030, 1050, 1075],
  },
];

export function storyBody(title, copy) {
  return (
    <section className="panel section">
      <div className="sectionHeader">
        <div>
          <div className="eyebrow">Story Surface</div>
          <h2>{title}</h2>
        </div>
        <span className="statusPill">Reviewable</span>
      </div>
      <p className="lede">{copy}</p>
    </section>
  );
}

export function retroStoryBody(title, copy) {
  return (
    <section className="retroPanel">
      <div className="retroSectionHeader">
        <div>
          <div className="retroEyebrow">Story Surface</div>
          <h2>{title}</h2>
        </div>
        <span className="retroTag" data-variant="ok">
          Stable
        </span>
      </div>
      <p className="retroLede">{copy}</p>
    </section>
  );
}
