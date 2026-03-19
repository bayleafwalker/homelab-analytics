import Link from "next/link";

function hasRequiredRole(user, requiredRole) {
  const roleOrder = { reader: 0, operator: 1, admin: 2 };
  return roleOrder[user?.role] >= roleOrder[requiredRole];
}

function navItemsForUser(user) {
  const items = [
    { href: "/", label: "Dashboard" },
    { href: "/runs", label: "Runs" },
    { href: "/review", label: "Review" },
    { href: "/reports", label: "Reports" }
  ];
  if (hasRequiredRole(user, "operator")) {
    items.push({ href: "/upload", label: "Upload" });
  }
  if (user?.role === "admin") {
    items.push({ href: "/control", label: "Control" });
  }
  return items;
}

export function AppShell({ currentPath, user, title, eyebrow, lede, children }) {
  const navItems = navItemsForUser(user);
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
            {navItems.map((item) => (
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
