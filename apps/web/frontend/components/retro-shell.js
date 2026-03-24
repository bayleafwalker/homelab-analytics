import Link from "next/link";

function navItemsForUser(user) {
  const items = [
    { href: "/retro", label: "Overview", prefix: "/retro" },
    { href: "/retro/money", label: "Money", prefix: "/retro/money" },
    { href: "/retro/utilities", label: "Utilities", prefix: "/retro/utilities" },
    { href: "/retro/operations", label: "Operations", prefix: "/retro/operations" },
  ];
  if (user?.role === "admin") {
    items.push(
      { href: "/retro/control", label: "Control", prefix: "/retro/control" },
      { href: "/retro/control/catalog", label: "Catalog", prefix: "/retro/control/catalog" },
      { href: "/retro/control/execution", label: "Execution", prefix: "/retro/control/execution" },
      { href: "/retro/terminal", label: "Terminal", prefix: "/retro/terminal" },
    );
  }
  return items;
}

function isActive(currentPath, item) {
  if (item.href === "/retro") {
    return currentPath === "/retro";
  }
  return currentPath === item.href || currentPath.startsWith(`${item.prefix}/`);
}

export function RetroShell({ currentPath, user, title, eyebrow, lede, children }) {
  const navItems = navItemsForUser(user);
  const renderedAt = new Date().toISOString().replace("T", " ").slice(0, 19);

  return (
    <main className="retroPage">
      <header className="retroHeader retroPanel">
        <div className="retroBrand">
          <div className="retroEyebrow">{eyebrow || "Parallel Retro Shell"}</div>
          <h1>{title || "Homelab Analytics // CRT"}</h1>
          {lede ? <p className="retroLede">{lede}</p> : null}
        </div>
        <div className="retroChrome">
          <div className="retroStatusBar" aria-label="Retro status strip">
            <span className="retroStatusCell">LINK: STABLE</span>
            <span className="retroStatusCell">RENDERER: WEB-CRT</span>
            <span className="retroStatusCell">STAMP: {renderedAt}</span>
          </div>
          <nav className="retroNav" aria-label="Retro navigation">
            {navItems.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className="retroNavLink"
                data-active={isActive(currentPath, item)}
              >
                {item.label}
              </Link>
            ))}
          </nav>
          <div className="retroActionRow">
            <Link className="retroActionLink" href="/">
              Classic
            </Link>
            <span className="retroUserBadge">
              {user.username} / {user.role}
            </span>
            <form action="/auth/logout" method="post">
              <button className="retroActionButton" type="submit">
                Sign Out
              </button>
            </form>
          </div>
        </div>
      </header>
      <section className="retroStack">{children}</section>
    </main>
  );
}
