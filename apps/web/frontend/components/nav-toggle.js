"use client";

import React, { useEffect, useState } from "react";

// Narrow-screen menu button for the shell rail. The rail is always rendered;
// below the rail breakpoint CSS hides it unless data-open="true".
export function NavToggle({ controls }) {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const rail = document.getElementById(controls);
    if (rail) rail.dataset.open = open ? "true" : "false";
  }, [controls, open]);

  useEffect(() => {
    if (!open) return undefined;
    function onKeyDown(event) {
      if (event.key === "Escape") setOpen(false);
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open]);

  return (
    <button
      type="button"
      className="navToggle"
      aria-expanded={open}
      aria-controls={controls}
      onClick={() => setOpen((value) => !value)}
    >
      {open ? "Close menu" : "Menu"}
    </button>
  );
}
