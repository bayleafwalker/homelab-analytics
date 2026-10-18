"use client";

import React, { useEffect, useRef } from "react";

// Native <details>/<summary> disclosure, so the explanation opens with Enter
// or Space and works with JavaScript off. This client layer only adds the
// popover manners: Escape closes it and returns focus to the trigger, and a
// click or tap outside closes it.
export function ExplainDisclosure({ label, placement = "end", tone = "default", children }) {
  const ref = useRef(null);

  useEffect(() => {
    const details = ref.current;
    if (!details) return undefined;
    const summary = details.querySelector("summary");

    function onKeyDown(event) {
      if (event.key === "Escape" && details.open) {
        event.stopPropagation();
        details.open = false;
        summary?.focus();
      }
    }
    function onPointerDown(event) {
      if (details.open && !details.contains(event.target)) details.open = false;
    }
    details.addEventListener("keydown", onKeyDown);
    document.addEventListener("pointerdown", onPointerDown);
    return () => {
      details.removeEventListener("keydown", onKeyDown);
      document.removeEventListener("pointerdown", onPointerDown);
    };
  }, []);

  return (
    <details ref={ref} className="explain" data-placement={placement} data-tone={tone}>
      <summary className="explainTrigger">
        <svg className="explainGlyph" viewBox="0 0 16 16" width="14" height="14" aria-hidden="true" focusable="false">
          <circle cx="3" cy="3" r="2" />
          <circle cx="13" cy="8" r="2" />
          <circle cx="3" cy="13" r="2" />
          <path d="M5 3.6 11 7.2M5 12.4 11 8.8" />
        </svg>
        <span className="explainTriggerText">Explain</span>
        <span className="srOnly"> {label}</span>
      </summary>
      <div className="explainPanel">{children}</div>
    </details>
  );
}
