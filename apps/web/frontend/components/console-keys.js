"use client";

import { useEffect } from "react";

// F1-F5 move focus to the console panel whose data-fkey matches. Cmd/Ctrl+K
// is not handled here: the command stub hosts the shared <CommandPalette>,
// whose own listener opens it, so there is exactly one Cmd+K handler.
export const CONSOLE_FKEYS = ["F1", "F2", "F3", "F4", "F5"];

export function focusConsolePanel(root, key) {
  const panel = root?.querySelector?.(`[data-panel-id][data-fkey="${key}"]`);
  if (!panel) return false;
  panel.focus();
  return true;
}

export function ConsoleKeys() {
  useEffect(() => {
    function onKeyDown(event) {
      if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
      if (!CONSOLE_FKEYS.includes(event.key)) return;
      if (document.querySelector("dialog[open]")) return;
      if (focusConsolePanel(document, event.key)) event.preventDefault();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);
  return null;
}
