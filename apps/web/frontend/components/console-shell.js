import React from "react";
import Link from "next/link";

import { ConsoleKeys } from "./console-keys";

// <ConsoleShell> — the Ops Console frame: one status bar, then a 3x2 grid
// (1.1fr 1.4fr 1fr / 1fr 1fr, 10px gap) that fits one 1440x900 screen.
//
// It mirrors RetroShell's structure (brand, status strip, actions) with the
// retro tokens, but is a sibling, not a subcomponent: no RetroShell nav, no
// CRT vignette. Panels are <ConsolePanel>s; F1-F5 focus them by data-fkey.

export function ConsolePanel({ id, title, fkey, area, headerExtra, footer, children, className = "" }) {
  const titleId = `console-${id}-title`;
  return (
    <section
      className={`consolePanel ${className}`.trim()}
      data-panel-id={id}
      data-fkey={fkey || undefined}
      data-area={area || id}
      tabIndex={-1}
      aria-labelledby={titleId}
    >
      <header className="consolePanelHead">
        <h2 id={titleId} className="consolePanelTitle">
          {title}
        </h2>
        {fkey ? (
          <kbd className="consoleKey">
            <span className="srOnly">shortcut </span>
            {fkey}
          </kbd>
        ) : null}
        {headerExtra}
      </header>
      <div className="consolePanelBody">{children}</div>
      {footer ? <footer className="consolePanelFoot">{footer}</footer> : null}
    </section>
  );
}

export function ConsoleShell({ title = "Ops console", user, stamp, status = [], children }) {
  return (
    <div className="console">
      <header className="consoleBar">
        <div className="consoleBrand">
          <span className="consoleEyebrow">Kotona</span>
          <h1 className="consoleTitle">{title}</h1>
        </div>
        <ul className="consoleStatus" aria-label="Console status">
          {status.map((cell) => (
            <li key={cell.label} className="consoleStatusCell" data-tone={cell.tone || "neutral"}>
              <span className="consoleStatusLabel">{cell.label}</span> {cell.value}
            </li>
          ))}
          {stamp ? (
            <li className="consoleStatusCell">
              <span className="consoleStatusLabel">stamp</span> <time dateTime={stamp}>{String(stamp).replace("T", " ").slice(0, 16)}</time>
            </li>
          ) : null}
        </ul>
        <nav className="consoleActions" aria-label="Leave console">
          <Link className="consoleAction" href="/">
            Dashboard
          </Link>
          <Link className="consoleAction" href="/retro">
            Retro
          </Link>
          {user ? (
            <span className="consoleUser">
              {user.username} / {user.role}
            </span>
          ) : null}
        </nav>
      </header>
      <div className="consoleGrid">{children}</div>
      <ConsoleKeys />
    </div>
  );
}
