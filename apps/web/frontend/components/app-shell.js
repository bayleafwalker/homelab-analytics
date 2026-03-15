import Link from "next/link";

const NAV_ITEMS = [
  { href: "/", label: "Dashboard" },
  { href: "/runs", label: "Runs" },
  { href: "/reports", label: "Reports" }
];

export function AppShell({ currentPath, user, title, eyebrow, lede, children }) {
  return (
    <main className="page">
      <header className="topbar">
        <div className="brand">
          <div className="eyebrow">{eyebrow || "Authenticated Control Plane"}</div>
          <h1>{title || "Homelab Analytics"}</h1>
          {lede ? <div className="lede">{lede}</div> : null}
        </div>
        <div className="actions">
          <nav className="navLinks" aria-label="Primary">
            {NAV_ITEMS.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className="navLink"
                data-active={currentPath === item.href}
              >
                {item.label}
              </Link>
            ))}
          </nav>
          <span className="userBadge">
            {user.username} / {user.role}
          </span>
          <form action="/auth/logout" method="post">
            <button className="ghostButton" type="submit">
              Sign Out
            </button>
          </form>
        </div>
      </header>
      {children}
    </main>
  );
}
