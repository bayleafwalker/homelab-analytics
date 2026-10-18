import React from "react";
import Link from "next/link";

import { isActivePath, navGroupsForUser, paletteEntriesForUser } from "../lib/nav-model";
import { CommandPalette } from "./command-palette";
import { NavToggle } from "./nav-toggle";

const RAIL_ID = "shell-rail";

export function AppShell({ currentPath, user, title, eyebrow, lede, children }) {
  const groups = navGroupsForUser(user);
  const paletteEntries = paletteEntriesForUser(user);
  return (
    <div className="shell">
      <a className="skipLink" href="#main-content">
        Skip to content
      </a>
      <header className="rail" id={RAIL_ID} data-open="false">
        <Link href="/" className="wordmark" aria-label="Kotona home">
          Kotona
        </Link>
        <CommandPalette entries={paletteEntries} currentPath={currentPath} />
        <nav className="railNav" aria-label="Primary">
          {groups.map((group) => (
            <div className="railGroup" key={group.id}>
              <p className="railGroupLabel" id={`rail-group-${group.id}`}>
                {group.label}
              </p>
              <ul className="railList" aria-labelledby={`rail-group-${group.id}`}>
                {group.entries.map((item) => {
                  const active = isActivePath(item.href, currentPath);
                  return (
                    <li key={item.href}>
                      <Link
                        href={item.href}
                        className="navLink"
                        data-active={active}
                        aria-current={active ? "page" : undefined}
                      >
                        {item.label}
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </nav>
        {user ? (
          <div className="railFooter">
            <span className="userBadge">
              {user.username} / {user.role}
            </span>
            <div className="railFooterActions">
              <Link className="ghostButton" href="/retro">
                Retro
              </Link>
              <form action="/auth/logout" method="post">
                <button className="ghostButton" type="submit">
                  Sign Out
                </button>
              </form>
            </div>
          </div>
        ) : null}
      </header>
      <main className="page shellMain" id="main-content" tabIndex={-1}>
        <div className="mobileBar">
          <Link href="/" className="wordmark">
            Kotona
          </Link>
          <NavToggle controls={RAIL_ID} />
        </div>
        <header className="topbar">
          <div className="brand">
            <div className="eyebrow">{eyebrow || "Household operating picture"}</div>
            <h1>{title || "Homelab Analytics"}</h1>
            {lede ? <div className="lede">{lede}</div> : null}
          </div>
        </header>
        {children}
      </main>
    </div>
  );
}
