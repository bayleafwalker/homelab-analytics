import React from "react";

function resolveHref(href) {
  if (typeof href === "string") {
    return href;
  }
  if (href && typeof href === "object" && typeof href.pathname === "string") {
    return href.pathname;
  }
  return "#";
}

export default function Link({ href, children, ...props }) {
  return React.createElement(
    "a",
    {
      ...props,
      href: resolveHref(href),
    },
    children
  );
}
